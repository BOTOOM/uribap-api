from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from uribap_api.api.completion_schemas import MealCompletionCreate
from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanTransition,
)
from uribap_api.api.schemas import InvitationCreate
from uribap_api.application.completion_service import complete_entry
from uribap_api.application.event_service import list_activity, process_outbox
from uribap_api.application.invitation_service import create_invitation
from uribap_api.application.planning_service import (
    add_entry,
    create_plan,
    transition_plan,
)
from uribap_api.config import get_settings
from uribap_api.domain.events.policies import DomainEventKind
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.inventory.ledger import InventoryLocation
from uribap_api.domain.planning.policies import MealPlanAction
from uribap_api.domain.recipes.policies import RecipeMealType, RecipeVersionState
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.event_models import (
    DomainEvent,
    EmailDeliveryIntent,
)
from uribap_api.infrastructure.persistence.household_models import (
    EmailOutboxEntry,
    Household,
    HouseholdMember,
    OutboxKind,
    OutboxStatus,
)
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import InventoryLot
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeVersion,
    RecipeVersionIngredient,
)

WEEK = date(2029, 2, 5) + timedelta(weeks=int(uuid4().int % 200))


def _member(session: Session) -> tuple[Household, HouseholdMember]:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="C", locale="es", timezone="UTC"))
    member = HouseholdMember(
        household_id=household_id,
        user_id=user_id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(member)
    session.flush()
    household = session.get(Household, household_id)
    assert household is not None
    return household, member


def _ingredient(session: Session, household: Household, name: str) -> Ingredient:
    ingredient = Ingredient(
        id=uuid4(),
        household_id=household.id,
        name=name,
        normalized_name=f"{name}-{uuid4()}",
        dimension=IngredientDimension.MASS,
        base_unit="g",
    )
    session.add(ingredient)
    session.flush()
    return ingredient


def _version(
    session: Session,
    household: Household,
    member: HouseholdMember,
    ingredients: list[tuple[Ingredient, str, str, bool]],
) -> RecipeVersion:
    recipe = Recipe(
        id=uuid4(),
        household_id=household.id,
        name=f"Recipe {uuid4()}",
        normalized_name=str(uuid4()),
        created_by_user_id=member.user_id,
    )
    version = RecipeVersion(
        id=uuid4(),
        recipe_id=recipe.id,
        version_number=1,
        base_servings=2,
        prep_minutes=10,
        state=RecipeVersionState.PUBLISHED,
        created_by_user_id=member.user_id,
        published_by_user_id=member.user_id,
    )
    session.add_all([recipe, version])
    session.flush()
    for position, (ingredient, amount, unit, optional) in enumerate(ingredients):
        session.add(
            RecipeVersionIngredient(
                recipe_version_id=version.id,
                ingredient_id=ingredient.id,
                amount=Decimal(amount),
                unit=unit,
                position=position,
                optional=optional,
            )
        )
    session.flush()
    return version


def _plan_with_entry(
    session: Session,
    member: HouseholdMember,
    week: date,
    recipe_version: RecipeVersion,
    *,
    approve: bool = True,
) -> tuple:
    plan = create_plan(session, member, MealPlanCreate(week_start_date=week), None)
    plan_id = plan.payload["id"]
    version = plan.payload["version"]
    result = add_entry(
        session,
        member,
        plan_id,
        MealPlanEntryCreate(
            expected_version=version,
            planned_date=week,
            meal_type=RecipeMealType.DINNER,
            recipe_version_id=recipe_version.id,
            servings=2,
            position=0,
        ),
        None,
    )
    version = result.payload["version"]
    entry_id = result.payload["entries"][0]["id"]
    if approve:
        transition_plan(
            session,
            member,
            plan_id,
            MealPlanAction.PROPOSE,
            MealPlanTransition(expected_version=version),
            None,
        )
        transition_plan(
            session,
            member,
            plan_id,
            MealPlanAction.APPROVE,
            MealPlanTransition(expected_version=version + 1),
            None,
        )
    from uuid import UUID

    return UUID(plan_id), UUID(entry_id)


def _events(session: Session, household_id, kind: str | None = None) -> list[DomainEvent]:
    statement = select(DomainEvent).where(DomainEvent.household_id == household_id)
    if kind is not None:
        statement = statement.where(DomainEvent.kind == kind)
    return list(session.scalars(statement.order_by(DomainEvent.created_at)))


def _outbox_entry(session: Session, *, dedupe: str | None = None) -> EmailOutboxEntry:
    entry = EmailOutboxEntry(
        dedupe_key=dedupe or f"test:{uuid4()}",
        kind=OutboxKind.HOUSEHOLD_INVITATION,
        recipient_email="a@example.test",
        template_data={"body": "hi"},
    )
    session.add(entry)
    session.flush()
    return entry


def test_plan_approve_emits_event(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 50))
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        plan_id, _ = _plan_with_entry(session, member, week, version)
        session.commit()

        events = _events(session, household.id, DomainEventKind.PLAN_APPROVED.value)
        assert len(events) == 1
        assert events[0].aggregate_id == plan_id
        assert events[0].actor_user_id == member.user_id


def test_failed_mutation_emits_no_event(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 50))
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        _lot = InventoryLot(
            id=uuid4(),
            household_id=household.id,
            ingredient_id=rice.id,
            quantity_on_hand=Decimal("0.1"),
            unit="kg",
            location=InventoryLocation.PANTRY,
            available=True,
            expiration_date=None,
            created_by_user_id=member.user_id,
        )
        session.add(_lot)
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        with pytest.raises(DomainError):
            complete_entry(session, member, plan_id, entry_id, MealCompletionCreate(), None)
        events = _events(session, household.id, DomainEventKind.MEAL_COMPLETED.value)
        assert events == []


def test_complete_entry_emits_event(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 50))
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        session.add(
            InventoryLot(
                id=uuid4(),
                household_id=household.id,
                ingredient_id=rice.id,
                quantity_on_hand=Decimal("5"),
                unit="kg",
                location=InventoryLocation.PANTRY,
                available=True,
                expiration_date=None,
                created_by_user_id=member.user_id,
            )
        )
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        result = complete_entry(session, member, plan_id, entry_id, MealCompletionCreate(), None)
        session.commit()
        events = _events(session, household.id, DomainEventKind.MEAL_COMPLETED.value)
        assert len(events) == 1
        assert str(events[0].aggregate_id) == result.payload["id"]
        assert events[0].payload["line_count"] == 1


def test_list_activity_paginates_and_isolates(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 50))
    with Session(integration_engine) as session:
        household, member = _member(session)
        other_household, other_member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        _plan_with_entry(session, member, week, version)
        other_rice = _ingredient(session, other_household, "Pasta")
        other_version = _version(
            session, other_household, other_member, [(other_rice, "1", "kg", False)]
        )
        _plan_with_entry(session, other_member, week + timedelta(weeks=1), other_version)
        create_invitation(
            session,
            household_id=household.id,
            inviter=member,
            payload=InvitationCreate(
                email=f"{uuid4()}@example.test", role="member", expires_in_hours=24
            ),
            request_id="req-test",
        )
        session.commit()

        entries, has_more, summary = list_activity(session, member, page=1, page_size=20)
        kinds = {entry.kind for entry in entries}
        assert DomainEventKind.PLAN_APPROVED.value in kinds
        assert all(entry.household_id == household.id for entry in entries)
        assert summary["pending"] == 1

        page1, more1, _ = list_activity(session, member, page=1, page_size=1)
        assert more1 is True
        page2, more2, _ = list_activity(session, member, page=2, page_size=1)
        assert more2 is False
        assert page1[0].id != page2[0].id


def test_invitation_emits_event_and_outbox(integration_engine) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session)
        session.commit()

        invitation, _raw, outbox = create_invitation(
            session,
            household_id=household.id,
            inviter=member,
            payload=InvitationCreate(
                email=f"{uuid4()}@example.test", role="member", expires_in_hours=24
            ),
            request_id="req-test",
        )
        session.commit()
        assert invitation.id is not None
        assert outbox.status == OutboxStatus.PENDING

        events = _events(session, household.id, DomainEventKind.INVITATION_CREATED.value)
        assert len(events) == 1

        # outbox summary sees the pending invitation intent
        _entries, _more, summary = list_activity(session, member, page=1, page_size=5)
        assert summary["pending"] == 1


def test_process_outbox_suppresses_without_smtp(
    integration_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def _boom(*args: object, **kwargs: object) -> None:
        calls.append(args)
        raise AssertionError("SMTP must not be called while delivery is disabled")

    monkeypatch.setattr("uribap_api.application.event_service.send_outbox_entry", _boom)
    with Session(integration_engine) as session:
        household, member = _member(session)
        entry = _outbox_entry(session)
        session.commit()

        settings = get_settings()
        assert settings.email_delivery_enabled is False
        result = process_outbox(session, settings, limit=10)
        assert calls == []
        assert result.claimed >= 1
        assert result.suppressed >= 1

        session.refresh(entry)
        assert entry.status == OutboxStatus.SUPPRESSED
        assert entry.attempts == 1
        intents = list(
            session.scalars(
                select(EmailDeliveryIntent).where(
                    EmailDeliveryIntent.email_outbox_entry_id == entry.id
                )
            )
        )
        assert len(intents) == 1
        assert intents[0].outcome == "suppressed"
        assert intents[0].subject == "Uribap household invitation"

        # rerun never touches suppressed entries
        process_outbox(session, settings, limit=10)
        session.refresh(entry)
        assert entry.status == OutboxStatus.SUPPRESSED
        remaining = session.scalar(
            select(func.count())
            .select_from(EmailDeliveryIntent)
            .where(EmailDeliveryIntent.email_outbox_entry_id == entry.id)
        )
        assert remaining == 1


def test_process_outbox_respects_limit(integration_engine) -> None:
    with Session(integration_engine) as session:
        _member(session)
        for _ in range(3):
            _outbox_entry(session)
        session.commit()

        pending_before = session.scalar(
            select(func.count())
            .select_from(EmailOutboxEntry)
            .where(EmailOutboxEntry.status == OutboxStatus.PENDING)
        )
        assert pending_before is not None
        settings = get_settings()
        result = process_outbox(session, settings, limit=2)
        assert result.claimed == 2
        assert result.suppressed == 2
        pending_after = session.scalar(
            select(func.count())
            .select_from(EmailOutboxEntry)
            .where(EmailOutboxEntry.status == OutboxStatus.PENDING)
        )
        assert pending_after == pending_before - 2
