from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanEntryUpdate,
    MealPlanTransition,
)
from uribap_api.application.planning_service import (
    add_entry,
    create_plan,
    delete_entry,
    list_entries,
    transition_plan,
    update_entry,
)
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.planning.policies import MealPlanAction
from uribap_api.domain.recipes.policies import RecipeMealType, RecipeVersionState
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.planning_models import MealPlan
from uribap_api.infrastructure.persistence.recipe_models import Recipe, RecipeVersion

WEEK = date(2026, 10, 5) + timedelta(days=7)


def _member(
    session: Session, role: MembershipRole = MembershipRole.OWNER
) -> tuple[Household, HouseholdMember]:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="Svc", locale="es", timezone="UTC"))
    member = HouseholdMember(
        household_id=household_id,
        user_id=user_id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    session.add(member)
    session.flush()
    household = session.get(Household, household_id)
    assert household is not None
    return household, member


def _second_member(session: Session, household: Household) -> HouseholdMember:
    user_id = uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    member = HouseholdMember(
        household_id=household.id,
        user_id=user_id,
        role=MembershipRole.MEMBER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(member)
    session.flush()
    return member


def _published_version(
    session: Session, household: Household, member: HouseholdMember
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
        prep_minutes=15,
        state=RecipeVersionState.PUBLISHED,
        created_by_user_id=member.user_id,
        published_by_user_id=member.user_id,
    )
    session.add_all([recipe, version])
    session.flush()
    return version


@pytest.mark.integration
def test_plan_entry_flow_and_optimistic_version(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 500))
    with Session(integration_engine) as session:
        household, member = _member(session)
        version = _published_version(session, household, member)
        session.commit()

        result = create_plan(session, member, MealPlanCreate(week_start_date=week), None)
        assert result.payload["state"] == "draft"
        assert result.payload["version"] == 1
        plan_id = result.payload["id"]

        result = add_entry(
            session,
            member,
            plan_id,
            MealPlanEntryCreate(
                expected_version=1,
                planned_date=week,
                meal_type=RecipeMealType.DINNER,
                recipe_version_id=version.id,
                servings=2,
            ),
            None,
        )
        assert result.payload["version"] == 2
        assert len(result.payload["entries"]) == 1

        with pytest.raises(DomainError) as stale:
            add_entry(
                session,
                member,
                plan_id,
                MealPlanEntryCreate(
                    expected_version=1,
                    planned_date=week,
                    meal_type=RecipeMealType.LUNCH,
                    recipe_version_id=version.id,
                    servings=2,
                ),
                None,
            )
        assert stale.value.status_code == 409

        result = transition_plan(
            session,
            member,
            plan_id,
            MealPlanAction.PROPOSE,
            MealPlanTransition(expected_version=2),
            None,
        )
        assert result.payload["state"] == "proposed"

        with pytest.raises(DomainError) as locked:
            add_entry(
                session,
                member,
                plan_id,
                MealPlanEntryCreate(
                    expected_version=result.payload["version"],
                    planned_date=week,
                    meal_type=RecipeMealType.BREAKFAST,
                    recipe_version_id=version.id,
                    servings=1,
                ),
                None,
            )
        assert locked.value.status_code == 409


@pytest.mark.integration
def test_idempotent_replay_returns_stored_payload(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 500) + 600)
    with Session(integration_engine) as session:
        household, member = _member(session)
        version = _published_version(session, household, member)
        session.commit()
        key = f"replay-{uuid4()}"

        first = create_plan(session, member, MealPlanCreate(week_start_date=week), key)
        entry_payload = MealPlanEntryCreate(
            expected_version=first.payload["version"],
            planned_date=week,
            meal_type=RecipeMealType.DINNER,
            recipe_version_id=version.id,
            servings=2,
        )
        created = add_entry(session, member, first.payload["id"], entry_payload, key)
        replayed = add_entry(session, member, first.payload["id"], entry_payload, key)
        assert replayed.payload == created.payload

        entries = list_entries(session, member, first.payload["id"])
        assert len(entries) == 1

        with pytest.raises(DomainError) as conflict:
            add_entry(
                session,
                member,
                first.payload["id"],
                MealPlanEntryCreate(
                    expected_version=created.payload["version"],
                    planned_date=week + timedelta(days=1),
                    meal_type=RecipeMealType.LUNCH,
                    recipe_version_id=version.id,
                    servings=3,
                ),
                key,
            )
        assert conflict.value.status_code == 409


@pytest.mark.integration
def test_duplicate_active_week_conflicts(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 500) + 1200)
    with Session(integration_engine) as session:
        _household, member = _member(session)
        session.commit()
        create_plan(session, member, MealPlanCreate(week_start_date=week), None)
        with pytest.raises(DomainError) as duplicate:
            create_plan(session, member, MealPlanCreate(week_start_date=week), None)
        assert duplicate.value.status_code == 409


@pytest.mark.integration
def test_update_entry_clears_notes_and_changes_version(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 500) + 1800)
    with Session(integration_engine) as session:
        household, member = _member(session)
        version = _published_version(session, household, member)
        session.commit()
        plan = create_plan(session, member, MealPlanCreate(week_start_date=week), None)
        created = add_entry(
            session,
            member,
            plan.payload["id"],
            MealPlanEntryCreate(
                expected_version=1,
                planned_date=week,
                meal_type=RecipeMealType.DINNER,
                recipe_version_id=version.id,
                servings=2,
                notes="no salt",
            ),
            None,
        )
        entry_id = created.payload["entries"][0]["id"]
        updated = update_entry(
            session,
            member,
            plan.payload["id"],
            entry_id,
            MealPlanEntryUpdate.model_validate(
                {"expected_version": created.payload["version"], "notes": None}
            ),
            None,
        )
        assert updated.payload["entries"][0]["notes"] is None

        other = _published_version(session, household, member)
        swapped = update_entry(
            session,
            member,
            plan.payload["id"],
            entry_id,
            MealPlanEntryUpdate(
                expected_version=updated.payload["version"], recipe_version_id=other.id
            ),
            None,
        )
        assert swapped.payload["entries"][0]["recipe_version_id"] == str(other.id)


@pytest.mark.integration
def test_approval_separation_and_reopen_note(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 500) + 2400)
    with Session(integration_engine) as session:
        household, owner = _member(session)
        approver = _second_member(session, household)
        session.commit()
        plan = create_plan(session, owner, MealPlanCreate(week_start_date=week), None)
        plan_id = plan.payload["id"]

        proposed = transition_plan(
            session,
            owner,
            plan_id,
            MealPlanAction.PROPOSE,
            MealPlanTransition(expected_version=plan.payload["version"]),
            None,
        )
        with pytest.raises(DomainError) as self_approve:
            transition_plan(
                session,
                owner,
                plan_id,
                MealPlanAction.APPROVE,
                MealPlanTransition(expected_version=proposed.payload["version"]),
                None,
            )
        assert self_approve.value.status_code == 409

        approved = transition_plan(
            session,
            approver,
            plan_id,
            MealPlanAction.APPROVE,
            MealPlanTransition(expected_version=proposed.payload["version"]),
            None,
        )
        assert approved.payload["state"] == "approved"

        with pytest.raises(DomainError) as missing_note:
            transition_plan(
                session,
                owner,
                plan_id,
                MealPlanAction.REOPEN,
                MealPlanTransition(expected_version=approved.payload["version"]),
                None,
            )
        assert missing_note.value.status_code == 422

        reopened = transition_plan(
            session,
            owner,
            plan_id,
            MealPlanAction.REOPEN,
            MealPlanTransition(expected_version=approved.payload["version"], note="plans changed"),
            None,
        )
        assert reopened.payload["state"] == "draft"


@pytest.mark.integration
def test_delete_entry_bumps_version(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 500) + 3000)
    with Session(integration_engine) as session:
        household, member = _member(session)
        version = _published_version(session, household, member)
        session.commit()
        plan = create_plan(session, member, MealPlanCreate(week_start_date=week), None)
        created = add_entry(
            session,
            member,
            plan.payload["id"],
            MealPlanEntryCreate(
                expected_version=1,
                planned_date=week,
                meal_type=RecipeMealType.SNACK,
                recipe_version_id=version.id,
                servings=1,
            ),
            None,
        )
        entry_id = created.payload["entries"][0]["id"]
        removed = delete_entry(
            session,
            member,
            plan.payload["id"],
            entry_id,
            created.payload["version"],
            None,
        )
        assert removed.payload["entries"] == []
        assert removed.payload["version"] == created.payload["version"] + 1
        stored = session.get(MealPlan, plan.payload["id"])
        assert stored is not None
        assert stored.version == removed.payload["version"]
