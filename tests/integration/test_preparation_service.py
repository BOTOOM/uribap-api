from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanTransition,
)
from uribap_api.api.preparation_schemas import PreparationRuleCreate, PreparationTaskCreate
from uribap_api.application.planning_service import (
    add_entry,
    create_plan,
    transition_plan,
)
from uribap_api.application.preparation_service import (
    add_rule,
    create_manual_task,
    delete_rule,
    list_tasks,
    transition_task,
)
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.planning.policies import MealPlanAction
from uribap_api.domain.preparation.policies import (
    PreparationTaskAction,
    PreparationTaskOrigin,
    PreparationTaskStatus,
    PreparationTaskType,
)
from uribap_api.domain.recipes.policies import (
    PreparationRuleType,
    RecipeMealType,
    RecipeVersionState,
)
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.planning_models import MealPlan
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipePreparationRule,
    RecipeVersion,
)

WEEK = date(2027, 6, 7) + timedelta(weeks=int(uuid4().int % 200))


def _member(session: Session, timezone: str = "UTC") -> tuple[Household, HouseholdMember]:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="P", locale="es", timezone=timezone))
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
    *,
    state: RecipeVersionState = RecipeVersionState.PUBLISHED,
    rules: list[tuple[PreparationRuleType, Ingredient | None, int, str]] | None = None,
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
        state=state,
        created_by_user_id=member.user_id,
        published_by_user_id=member.user_id if state == RecipeVersionState.PUBLISHED else None,
    )
    session.add_all([recipe, version])
    session.flush()
    for rule_type, ingredient, lead, instruction in rules or []:
        session.add(
            RecipePreparationRule(
                recipe_version_id=version.id,
                rule_type=rule_type,
                ingredient_id=ingredient.id if ingredient else None,
                lead_minutes=lead,
                instruction=instruction,
            )
        )
    session.flush()
    return version


def _approve_plan(
    session: Session,
    member: HouseholdMember,
    week: date,
    entries: list[tuple[date, RecipeMealType, RecipeVersion, int]],
) -> UUID:
    plan = create_plan(session, member, MealPlanCreate(week_start_date=week), None)
    plan_id = UUID(plan.payload["id"])
    version = plan.payload["version"]
    for position, (day, meal_type, recipe_version, servings) in enumerate(entries):
        result = add_entry(
            session,
            member,
            plan_id,
            MealPlanEntryCreate(
                expected_version=version,
                planned_date=day,
                meal_type=meal_type,
                recipe_version_id=recipe_version.id,
                servings=servings,
                position=position,
            ),
            None,
        )
        version = result.payload["version"]
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
    return plan_id


def test_approve_derives_tasks_with_due_at(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100))
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(
            session,
            household,
            member,
            rules=[
                (PreparationRuleType.DEFROST, rice, 720, "Take out of freezer"),
                (PreparationRuleType.SOAK, None, 0, "Rinse"),
            ],
        )
        session.commit()

        _approve_plan(session, member, week, [(week, RecipeMealType.DINNER, version, 2)])
        session.commit()

        items = list_tasks(session, member, None, None, None)
        assert len(items) == 2
        by_type = {item.task_type: item for item in items}
        # dinner 20:00 UTC - 12h = 08:00 UTC
        assert by_type[PreparationTaskType.DEFROST].due_at == datetime(
            week.year, week.month, week.day, 8, 0, tzinfo=UTC
        )
        assert by_type[PreparationTaskType.SOAK].due_at == datetime(
            week.year, week.month, week.day, 20, 0, tzinfo=UTC
        )
        for item in items:
            assert item.origin == PreparationTaskOrigin.DERIVED
            assert item.status == PreparationTaskStatus.PENDING
            assert item.version == 1
            assert item.meal_plan_entry_id is not None
            assert item.planned_date == week
            assert item.meal_type == RecipeMealType.DINNER
            assert item.recipe_name is not None
        assert by_type[PreparationTaskType.DEFROST].ingredient_name == "Rice"
        assert by_type[PreparationTaskType.DEFROST].instruction == "Take out of freezer"


def test_reapproval_is_idempotent_and_cancels_stale(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 150)
    with Session(integration_engine) as session:
        household, member = _member(session)
        version = _version(
            session,
            household,
            member,
            rules=[
                (PreparationRuleType.MARINATE, None, 60, "Marinate"),
                (PreparationRuleType.PREPARE_AHEAD, None, 30, "Chop"),
            ],
        )
        session.commit()
        plan_id = _approve_plan(session, member, week, [(week, RecipeMealType.LUNCH, version, 2)])
        session.commit()

        tasks = list_tasks(session, member, None, None, None)
        assert len(tasks) == 2

        # complete one derived task, delete the rule for the other, re-approve
        marinade = next(t for t in tasks if t.task_type == PreparationTaskType.MARINATE)
        transition_task(
            session,
            member,
            marinade.id,
            PreparationTaskAction.COMPLETE,
            marinade.version,
            None,
        )
        rule_to_delete = session.scalars(
            select(RecipePreparationRule).where(
                RecipePreparationRule.recipe_version_id == version.id,
                RecipePreparationRule.rule_type == PreparationRuleType.PREPARE_AHEAD,
            )
        ).one()
        plan = session.get(MealPlan, plan_id)
        assert plan is not None
        session.delete(rule_to_delete)
        session.commit()

        # draft -> propose -> approve again
        transition_plan(
            session,
            member,
            plan_id,
            MealPlanAction.REOPEN,
            MealPlanTransition(expected_version=plan.version, note="adjust"),
            None,
        )
        plan = session.get(MealPlan, plan_id)
        assert plan is not None
        transition_plan(
            session,
            member,
            plan_id,
            MealPlanAction.PROPOSE,
            MealPlanTransition(expected_version=plan.version),
            None,
        )
        plan = session.get(MealPlan, plan_id)
        assert plan is not None
        transition_plan(
            session,
            member,
            plan_id,
            MealPlanAction.APPROVE,
            MealPlanTransition(expected_version=plan.version),
            None,
        )
        session.commit()

        items = list_tasks(session, member, None, None, None)
        # completed marinade untouched; pending prepare_ahead cancelled
        assert len(items) == 2
        by_type = {item.task_type: item for item in items}
        assert by_type[PreparationTaskType.MARINATE].status == (PreparationTaskStatus.COMPLETED)
        assert by_type[PreparationTaskType.PREPARE_AHEAD].status == (
            PreparationTaskStatus.CANCELLED
        )


def test_manual_task_validation_and_transition(integration_engine) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Beans")
        session.commit()
        due = datetime(2027, 7, 1, 9, 0, tzinfo=UTC)

        result = create_manual_task(
            session,
            member,
            PreparationTaskCreate(
                title="  Soak beans  ",
                instruction="Overnight",
                due_at=due,
                ingredient_id=rice.id,
                amount=Decimal("0.5"),
                unit="kg",
            ),
            "mk-1",
        )
        task = result.payload
        assert task["title"] == "Soak beans"
        assert task["task_type"] == "manual"
        assert task["amount"] == "0.500000"
        assert task["unit"] == "kg"

        # idempotent replay returns the stored payload
        replay = create_manual_task(
            session,
            member,
            PreparationTaskCreate(
                title="  Soak beans  ",
                instruction="Overnight",
                due_at=due,
                ingredient_id=rice.id,
                amount=Decimal("0.5"),
                unit="kg",
            ),
            "mk-1",
        )
        assert replay.payload == task

        # same key different body -> 409
        with pytest.raises(DomainError) as conflict:
            create_manual_task(
                session,
                member,
                PreparationTaskCreate(title="Different", due_at=due),
                "mk-1",
            )
        assert conflict.value.status_code == 409

        task_id = UUID(task["id"])
        # stale expected_version -> 409
        with pytest.raises(DomainError):
            transition_task(session, member, task_id, PreparationTaskAction.COMPLETE, 99, None)
        done = transition_task(session, member, task_id, PreparationTaskAction.COMPLETE, 1, None)
        assert done.payload["status"] == "completed"
        assert done.payload["version"] == 2
        assert done.payload["completed_by_user_id"] == str(member.user_id)
        # already completed -> 409
        with pytest.raises(DomainError):
            transition_task(session, member, task_id, PreparationTaskAction.CANCEL, 2, None)

        # validation errors
        with pytest.raises(DomainError) as excinfo:
            create_manual_task(
                session,
                member,
                PreparationTaskCreate(
                    title="Bad unit",
                    due_at=due,
                    ingredient_id=rice.id,
                    amount=Decimal("1"),
                    unit="ml",
                ),
                None,
            )
        assert excinfo.value.status_code == 422


def test_manual_task_ingredient_tenancy(integration_engine) -> None:
    with Session(integration_engine) as session:
        _household_a, member = _member(session)
        other_household, other_member = _member(session)
        foreign = _ingredient(session, other_household, "Foreign")
        session.commit()
        due = datetime(2027, 7, 2, 9, 0, tzinfo=UTC)

        with pytest.raises(DomainError) as forbidden:
            create_manual_task(
                session,
                member,
                PreparationTaskCreate(title="Steal", due_at=due, ingredient_id=foreign.id),
                None,
            )
        assert forbidden.value.status_code == 403

        with pytest.raises(DomainError) as not_found:
            create_manual_task(
                session,
                member,
                PreparationTaskCreate(title="Ghost", due_at=due, ingredient_id=uuid4()),
                None,
            )
        assert not_found.value.status_code == 404


def test_rule_management_draft_only_and_tenant(integration_engine) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session)
        other_household, other_member = _member(session)
        rice = _ingredient(session, household, "Rice")
        foreign = _ingredient(session, other_household, "Foreign")
        draft = _version(session, household, member, state=RecipeVersionState.DRAFT)
        published = _version(session, household, member)
        session.commit()

        recipe_id = session.get(RecipeVersion, draft.id).recipe_id  # type: ignore[union-attr]
        rule = add_rule(
            session,
            member,
            recipe_id,
            draft.id,
            PreparationRuleCreate(
                rule_type=PreparationRuleType.DEFROST,
                ingredient_id=rice.id,
                lead_minutes=600,
                instruction="Defrost",
            ),
        )
        assert rule.rule_type == PreparationRuleType.DEFROST
        assert rule.ingredient_name == "Rice"

        # published version rejects rule writes
        pub_recipe_id = session.get(RecipeVersion, published.id).recipe_id  # type: ignore[union-attr]
        with pytest.raises(DomainError) as excinfo:
            add_rule(
                session,
                member,
                pub_recipe_id,
                published.id,
                PreparationRuleCreate(
                    rule_type=PreparationRuleType.SOAK,
                    lead_minutes=10,
                    instruction="Soak",
                ),
            )
        assert excinfo.value.status_code == 422

        # cross-household ingredient -> 403
        with pytest.raises(DomainError) as excinfo:
            add_rule(
                session,
                member,
                recipe_id,
                draft.id,
                PreparationRuleCreate(
                    rule_type=PreparationRuleType.SOAK,
                    ingredient_id=foreign.id,
                    lead_minutes=10,
                    instruction="Soak",
                ),
            )
        assert excinfo.value.status_code == 403

        delete_rule(session, member, recipe_id, draft.id, rule.id)
        with pytest.raises(DomainError) as excinfo:
            delete_rule(session, member, recipe_id, draft.id, rule.id)
        assert excinfo.value.status_code == 404


def test_list_filters_and_tenant_isolation(integration_engine) -> None:
    with Session(integration_engine) as session:
        _ha, member = _member(session)
        _hb, other = _member(session)
        session.commit()
        early = datetime(2027, 8, 1, 8, 0, tzinfo=UTC)
        late = datetime(2027, 8, 5, 8, 0, tzinfo=UTC)
        create_manual_task(
            session, member, PreparationTaskCreate(title="Early", due_at=early), None
        )
        second = create_manual_task(
            session, member, PreparationTaskCreate(title="Late", due_at=late), None
        )
        create_manual_task(session, other, PreparationTaskCreate(title="Other", due_at=early), None)
        session.commit()

        items = list_tasks(session, member, None, None, None)
        assert [item.title for item in items] == ["Early", "Late"]
        assert all(item.origin == PreparationTaskOrigin.MANUAL for item in items)

        pending = list_tasks(session, member, PreparationTaskStatus.PENDING, None, None)
        assert len(pending) == 2
        completed = list_tasks(session, member, PreparationTaskStatus.COMPLETED, None, None)
        assert completed == []

        window = list_tasks(session, member, None, early, early + timedelta(hours=1))
        assert [item.title for item in window] == ["Early"]

        with pytest.raises(DomainError) as excinfo:
            list_tasks(session, member, None, late, early)
        assert excinfo.value.status_code == 422

        # other household cannot transition member's task
        with pytest.raises(DomainError) as excinfo:
            transition_task(
                session,
                other,
                UUID(second.payload["id"]),
                PreparationTaskAction.COMPLETE,
                1,
                None,
            )
        assert excinfo.value.status_code == 404


def test_derivation_uses_household_timezone(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 300)
    with Session(integration_engine) as session:
        household, member = _member(session, timezone="Europe/Madrid")
        version = _version(
            session,
            household,
            member,
            rules=[(PreparationRuleType.SOAK, None, 60, "Soak")],
        )
        session.commit()
        _approve_plan(session, member, week, [(week, RecipeMealType.BREAKFAST, version, 2)])
        session.commit()

        items = list_tasks(session, member, None, None, None)
        assert len(items) == 1
        # breakfast 08:00 local - 60m, converted to UTC with the week-appropriate offset
        local_start = datetime(
            week.year, week.month, week.day, 8, 0, tzinfo=ZoneInfo("Europe/Madrid")
        )
        assert items[0].due_at == (local_start - timedelta(minutes=60)).astimezone(UTC)


def test_no_tasks_without_rules(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 100) + 400)
    with Session(integration_engine) as session:
        household, member = _member(session)
        version = _version(session, household, member, rules=[])
        session.commit()
        _approve_plan(session, member, week, [(week, RecipeMealType.DINNER, version, 2)])
        session.commit()
        assert list_tasks(session, member, None, None, None) == []
