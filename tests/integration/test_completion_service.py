from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from uribap_api.api.completion_schemas import (
    CompletionActualLine,
    MealCompletionCreate,
)
from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanTransition,
)
from uribap_api.application.completion_service import (
    complete_entry,
    correct_line,
    get_completion,
    list_completions,
    reopen_completion,
)
from uribap_api.application.planning_service import (
    add_entry,
    create_plan,
    transition_plan,
)
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.inventory.ledger import (
    InventoryLocation,
    InventoryMovementType,
)
from uribap_api.domain.planning.policies import MealPlanAction
from uribap_api.domain.recipes.policies import (
    RecipeMealType,
    RecipeVersionState,
)
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import (
    Household,
    HouseholdMember,
)
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import (
    InventoryLot,
    InventoryMovement,
)
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeVersion,
    RecipeVersionIngredient,
)

WEEK = date(2028, 1, 3) + timedelta(weeks=int(uuid4().int % 200))
FAR_FUTURE = date.today() + timedelta(days=30)


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
    *,
    base_servings: int = 2,
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
        base_servings=base_servings,
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


def _lot(
    session: Session,
    member: HouseholdMember,
    ingredient: Ingredient,
    quantity: str,
    expiration: date | None,
    unit: str = "kg",
) -> InventoryLot:
    lot = InventoryLot(
        id=uuid4(),
        household_id=member.household_id,
        ingredient_id=ingredient.id,
        quantity_on_hand=Decimal(quantity),
        unit=unit,
        location=InventoryLocation.PANTRY,
        available=True,
        expiration_date=expiration,
        created_by_user_id=member.user_id,
    )
    session.add(lot)
    session.flush()
    return lot


def _plan_with_entry(
    session: Session,
    member: HouseholdMember,
    week: date,
    recipe_version: RecipeVersion,
    servings: int = 2,
    *,
    approve: bool = True,
) -> tuple[UUID, UUID]:
    plan = create_plan(session, member, MealPlanCreate(week_start_date=week), None)
    plan_id = UUID(plan.payload["id"])
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
            servings=servings,
            position=0,
        ),
        None,
    )
    version = result.payload["version"]
    entry_id = UUID(result.payload["entries"][0]["id"])
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
    return plan_id, entry_id


def _movements_for(session: Session, line_id: UUID) -> list[InventoryMovement]:
    return list(
        session.scalars(
            select(InventoryMovement)
            .where(
                InventoryMovement.source_type == "meal_completion_line",
                InventoryMovement.source_id == line_id,
            )
            .order_by(InventoryMovement.created_at, InventoryMovement.id)
        )
    )


def test_complete_entry_deducts_fefo(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100))
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        later = _lot(session, member, rice, "1", FAR_FUTURE + timedelta(days=5))
        earlier = _lot(session, member, rice, "0.8", FAR_FUTURE)
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        result = complete_entry(
            session, member, plan_id, entry_id, MealCompletionCreate(), None
        )
        payload = result.payload
        assert payload["state"] == "recorded"
        assert payload["version"] == 1
        assert payload["recipe_name"] is not None
        assert payload["planned_date"] == str(week)
        assert len(payload["lines"]) == 1
        line = payload["lines"][0]
        assert line["planned_amount"] == "0.500000"
        assert line["actual_amount"] == "0.500000"
        assert line["ingredient_name"] == "Rice"

        session.refresh(earlier)
        session.refresh(later)
        assert earlier.quantity_on_hand == Decimal("0.300000")
        assert later.quantity_on_hand == Decimal("1.000000")

        movements = _movements_for(session, UUID(line["id"]))
        assert len(movements) == 1
        assert movements[0].movement_type == InventoryMovementType.MEAL_CONSUMPTION
        assert movements[0].delta == Decimal("-0.500000")
        assert movements[0].lot_id == earlier.id
        assert movements[0].result_quantity_on_hand == Decimal("0.300000")


def test_complete_splits_across_lots_fefo(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 110)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Pasta")
        version = _version(session, household, member, [(rice, "1", "kg", False)])
        earlier = _lot(session, member, rice, "0.7", FAR_FUTURE)
        later = _lot(session, member, rice, "2", FAR_FUTURE + timedelta(days=5))
        expired = _lot(session, member, rice, "9", date.today() - timedelta(days=1))
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        complete_entry(session, member, plan_id, entry_id, MealCompletionCreate(), None)
        session.refresh(earlier)
        session.refresh(later)
        session.refresh(expired)
        assert earlier.quantity_on_hand == Decimal("0.000000")
        assert later.quantity_on_hand == Decimal("1.700000")
        assert expired.quantity_on_hand == Decimal("9.000000")


def test_complete_requires_approved_plan(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 210)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        _lot(session, member, rice, "5", None)
        plan_id, entry_id = _plan_with_entry(
            session, member, week, version, approve=False
        )
        session.commit()

        with pytest.raises(DomainError) as excinfo:
            complete_entry(session, member, plan_id, entry_id, MealCompletionCreate(), None)
        assert excinfo.value.status_code == 409


def test_complete_insufficient_stock_aborts(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 310)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "2", "kg", False)])
        lot = _lot(session, member, rice, "0.5", None)
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        with pytest.raises(DomainError) as excinfo:
            complete_entry(session, member, plan_id, entry_id, MealCompletionCreate(), None)
        assert excinfo.value.status_code == 409
        session.refresh(lot)
        assert lot.quantity_on_hand == Decimal("0.500000")
        assert list_completions(session, member, None, None, None, None) == []


def test_complete_explicit_lines_and_idempotent_replay(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 410)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        oil = _ingredient(session, household, "Oil")
        version = _version(
            session,
            household,
            member,
            [(rice, "0.5", "kg", False), (oil, "0.1", "kg", True)],
        )
        rice_lot = _lot(session, member, rice, "5", None)
        oil_lot = _lot(session, member, oil, "5", None)
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        payload = MealCompletionCreate(
            lines=[
                CompletionActualLine(
                    ingredient_id=rice.id, actual_amount=Decimal("0.7"), unit="kg"
                )
            ]
        )
        result = complete_entry(session, member, plan_id, entry_id, payload, "ck-1")
        # optional oil line dropped when explicit lines do not cover it
        assert len(result.payload["lines"]) == 1
        assert result.payload["lines"][0]["actual_amount"] == "0.700000"
        session.refresh(rice_lot)
        session.refresh(oil_lot)
        assert rice_lot.quantity_on_hand == Decimal("4.300000")
        assert oil_lot.quantity_on_hand == Decimal("5.000000")

        replay = complete_entry(session, member, plan_id, entry_id, payload, "ck-1")
        assert replay.payload == result.payload
        session.refresh(rice_lot)
        assert rice_lot.quantity_on_hand == Decimal("4.300000")

        with pytest.raises(DomainError) as conflict:
            complete_entry(
                session,
                member,
                plan_id,
                entry_id,
                MealCompletionCreate(),
                "ck-1",
            )
        assert conflict.value.status_code == 409

        # a different key still cannot double-complete the entry
        with pytest.raises(DomainError) as duplicate:
            complete_entry(
                session,
                member,
                plan_id,
                entry_id,
                MealCompletionCreate(),
                "ck-2",
            )
        assert duplicate.value.status_code == 409


def test_correct_line_reverses_and_rededucts(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 510)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        lot = _lot(session, member, rice, "5", None)
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        created = complete_entry(
            session, member, plan_id, entry_id, MealCompletionCreate(), None
        )
        completion_id = UUID(created.payload["id"])
        line_id = UUID(created.payload["lines"][0]["id"])
        session.refresh(lot)
        assert lot.quantity_on_hand == Decimal("4.500000")

        corrected = correct_line(
            session,
            member,
            completion_id,
            line_id,
            expected_version=1,
            actual_amount=Decimal("0.2"),
            unit="kg",
            idempotency_key=None,
        )
        assert corrected.payload["version"] == 2
        assert corrected.payload["lines"][0]["actual_amount"] == "0.200000"
        session.refresh(lot)
        assert lot.quantity_on_hand == Decimal("4.800000")

        movements = _movements_for(session, line_id)
        by_type = [m.movement_type for m in movements]
        assert by_type.count(InventoryMovementType.MEAL_CONSUMPTION) == 2
        assert by_type.count(InventoryMovementType.REVERSAL) == 1
        net = sum(Decimal(m.delta) for m in movements)
        assert net == Decimal("-0.200000")

        # a second correction nets correctly
        corrected2 = correct_line(
            session,
            member,
            completion_id,
            line_id,
            expected_version=2,
            actual_amount=Decimal("1"),
            unit="kg",
            idempotency_key=None,
        )
        assert corrected2.payload["lines"][0]["actual_amount"] == "1.000000"
        session.refresh(lot)
        assert lot.quantity_on_hand == Decimal("4.000000")

        # correcting a reopened/wrong-unit/stale version fails cleanly
        with pytest.raises(DomainError) as excinfo:
            correct_line(
                session,
                member,
                completion_id,
                line_id,
                expected_version=3,
                actual_amount=Decimal("1"),
                unit="g",
                idempotency_key=None,
            )
        assert excinfo.value.status_code == 422
        with pytest.raises(DomainError) as excinfo:
            correct_line(
                session,
                member,
                completion_id,
                line_id,
                expected_version=1,
                actual_amount=Decimal("1"),
                unit="kg",
                idempotency_key=None,
            )
        assert excinfo.value.status_code == 409


def test_reopen_restores_inventory_and_recompletion(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 610)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        lot = _lot(session, member, rice, "5", None)
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        created = complete_entry(
            session, member, plan_id, entry_id, MealCompletionCreate(), None
        )
        completion_id = UUID(created.payload["id"])
        session.refresh(lot)
        assert lot.quantity_on_hand == Decimal("4.500000")

        reopened = reopen_completion(
            session, member, completion_id, expected_version=1, reason="mistake",
            idempotency_key=None,
        )
        assert reopened.payload["state"] == "reopened"
        assert reopened.payload["version"] == 2
        assert reopened.payload["reopen_reason"] == "mistake"
        session.refresh(lot)
        assert lot.quantity_on_hand == Decimal("5.000000")

        # reopen again -> 409
        with pytest.raises(DomainError):
            reopen_completion(
                session, member, completion_id, expected_version=2, reason=None,
                idempotency_key=None,
            )
        # correct on reopened -> 409
        with pytest.raises(DomainError):
            correct_line(
                session,
                member,
                completion_id,
                UUID(created.payload["lines"][0]["id"]),
                expected_version=2,
                actual_amount=Decimal("1"),
                unit="kg",
                idempotency_key=None,
            )

        # the entry can be completed again as a new recorded row
        again = complete_entry(
            session, member, plan_id, entry_id, MealCompletionCreate(), None
        )
        assert again.payload["state"] == "recorded"
        assert again.payload["id"] != str(completion_id)

        items = list_completions(session, member, entry_id, None, None, None)
        assert len(items) == 2


def test_tenant_isolation(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 710)
    with Session(integration_engine) as session:
        household, member = _member(session)
        _other_household, other = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        _lot(session, member, rice, "5", None)
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        created = complete_entry(
            session, member, plan_id, entry_id, MealCompletionCreate(), None
        )
        completion_id = UUID(created.payload["id"])
        line_id = UUID(created.payload["lines"][0]["id"])

        with pytest.raises(DomainError) as excinfo:
            get_completion(session, other, completion_id)
        assert excinfo.value.status_code == 404
        with pytest.raises(DomainError) as excinfo:
            reopen_completion(
                session, other, completion_id, expected_version=1, reason=None,
                idempotency_key=None,
            )
        assert excinfo.value.status_code == 404
        with pytest.raises(DomainError) as excinfo:
            correct_line(
                session,
                other,
                completion_id,
                line_id,
                expected_version=1,
                actual_amount=Decimal("1"),
                unit="kg",
                idempotency_key=None,
            )
        assert excinfo.value.status_code == 404
        assert list_completions(session, other, entry_id, None, None, None) == []


def test_list_filters(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 810)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, [(rice, "0.5", "kg", False)])
        _lot(session, member, rice, "5", None)
        plan_id, entry_id = _plan_with_entry(session, member, week, version)
        session.commit()

        created = complete_entry(
            session, member, plan_id, entry_id, MealCompletionCreate(), None
        )
        completion_id = UUID(created.payload["id"])

        all_items = list_completions(session, member, None, None, None, None)
        assert [item.id for item in all_items] == [completion_id]

        from uribap_api.domain.completion.policies import MealCompletionState

        recorded = list_completions(
            session, member, None, MealCompletionState.RECORDED, None, None
        )
        assert len(recorded) == 1
        reopened = list_completions(
            session, member, None, MealCompletionState.REOPENED, None, None
        )
        assert reopened == []

        now = datetime.now(UTC)
        window = list_completions(
            session, member, None, None, now - timedelta(hours=1), now + timedelta(hours=1)
        )
        assert len(window) == 1
        with pytest.raises(DomainError) as excinfo:
            list_completions(
                session,
                member,
                None,
                None,
                now + timedelta(hours=1),
                now - timedelta(hours=1),
            )
        assert excinfo.value.status_code == 422
