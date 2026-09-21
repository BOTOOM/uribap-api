from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanTransition,
)
from uribap_api.application.forecast_service import demand_forecast
from uribap_api.application.planning_service import add_entry, create_plan, transition_plan
from uribap_api.domain.forecast.policies import DemandForecastError
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.inventory.ledger import InventoryLocation
from uribap_api.domain.planning.policies import MealPlanAction
from uribap_api.domain.recipes.policies import RecipeMealType, RecipeVersionState
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import InventoryLot
from uribap_api.infrastructure.persistence.planning_models import MealPlanOperation
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeVersion,
    RecipeVersionIngredient,
)

WEEK = date(2027, 2, 1) + timedelta(weeks=int(uuid4().int % 300))


def _member(session: Session) -> tuple[Household, HouseholdMember]:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="Fc", locale="es", timezone="UTC"))
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
    ingredient: Ingredient,
    amount: str,
    unit: str = "g",
    optional: bool = False,
    base: int = 2,
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
        base_servings=base,
        prep_minutes=10,
        state=RecipeVersionState.PUBLISHED,
        created_by_user_id=member.user_id,
        published_by_user_id=member.user_id,
    )
    line = RecipeVersionIngredient(
        recipe_version_id=version.id,
        ingredient_id=ingredient.id,
        amount=Decimal(amount),
        unit=unit,
        position=0,
        optional=optional,
    )
    session.add_all([recipe, version, line])
    session.flush()
    return version


def _approved_plan(
    session: Session,
    member: HouseholdMember,
    week: date,
    entries: list[tuple[date, RecipeVersion, int]],
) -> str:
    plan = create_plan(session, member, MealPlanCreate(week_start_date=week), None)
    plan_id = plan.payload["id"]
    version = plan.payload["version"]
    for position, (day, recipe_version, servings) in enumerate(entries):
        result = add_entry(
            session,
            member,
            plan_id,
            MealPlanEntryCreate(
                expected_version=version,
                planned_date=day,
                meal_type=RecipeMealType.DINNER,
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
    version += 1
    transition_plan(
        session,
        member,
        plan_id,
        MealPlanAction.APPROVE,
        MealPlanTransition(expected_version=version),
        None,
    )
    return plan_id


def _lot(
    session: Session,
    household: Household,
    member: HouseholdMember,
    ingredient: Ingredient,
    amount: str,
    expires: date | None = None,
) -> None:
    session.add(
        InventoryLot(
            household_id=household.id,
            ingredient_id=ingredient.id,
            quantity_on_hand=Decimal(amount),
            unit="g",
            location=InventoryLocation.PANTRY,
            available=True,
            expiration_date=expires,
            created_by_user_id=member.user_id,
        )
    )
    session.flush()


@pytest.mark.integration
def test_demand_forecast_scales_and_reports_shortfall(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 400)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "Rice")
        version = _version(session, household, member, rice, "100", base=2)
        _lot(session, household, member, rice, "50", expires=week)
        _lot(session, household, member, rice, "999", expires=week - timedelta(days=1))
        session.commit()

        plan_id = _approved_plan(session, member, week, [(week, version, 4)])
        session.commit()

        # 4 servings / base 2 -> factor 2 -> demand 200 g; only the unexpired lot counts.
        result = demand_forecast(session, member, week, week + timedelta(days=6))
        assert result.considered_plan_ids == [UUID(plan_id)]
        assert len(result.items) == 1
        line = result.items[0]
        assert line.ingredient_id == rice.id
        assert line.ingredient_name == "Rice"
        assert line.required_amount == Decimal("200.000000")
        assert line.on_hand_amount == Decimal("50.000000")
        assert line.shortfall_amount == Decimal("150.000000")


@pytest.mark.integration
def test_draft_plan_contributes_nothing(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 700)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "DraftRice")
        version = _version(session, household, member, rice, "80", base=2)
        session.commit()
        plan = create_plan(session, member, MealPlanCreate(week_start_date=week), None)
        add_entry(
            session,
            member,
            plan.payload["id"],
            MealPlanEntryCreate(
                expected_version=1,
                planned_date=week,
                meal_type=RecipeMealType.LUNCH,
                recipe_version_id=version.id,
                servings=2,
            ),
            None,
        )
        session.commit()

        result = demand_forecast(session, member, week, week + timedelta(days=6))
        assert result.considered_plan_ids == []
        assert result.items == []


@pytest.mark.integration
def test_forecast_is_deterministic_and_read_only(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 1000)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "DetRice")
        version = _version(session, household, member, rice, "30", base=3)
        session.commit()
        _approved_plan(session, member, week, [(week, version, 3), (week, version, 6)])
        session.commit()

        first = demand_forecast(session, member, week, week + timedelta(days=6))
        second = demand_forecast(session, member, week, week + timedelta(days=6))
        assert first.model_dump() == second.model_dump()
        # factor 1 and 2 -> 30 + 60 = 90
        assert first.items[0].required_amount == Decimal("90.000000")
        receipts = session.scalar(
            select(func.count())
            .select_from(MealPlanOperation)
            .where(MealPlanOperation.operation == "forecast_demand")
        )
        assert receipts == 0


@pytest.mark.integration
def test_forecast_window_validation_and_tenant_isolation(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 1300)
    with Session(integration_engine) as session:
        household, member = _member(session)
        other_household, other = _member(session)
        rice = _ingredient(session, other_household, "OtherRice")
        version = _version(session, other_household, other, rice, "40", base=2)
        session.commit()
        _approved_plan(session, other, week, [(week, version, 2)])
        session.commit()

        with pytest.raises(DemandForecastError):
            demand_forecast(session, member, week + timedelta(days=6), week)
        with pytest.raises(DemandForecastError):
            demand_forecast(session, member, week, week + timedelta(days=62))

        result = demand_forecast(session, member, week, week + timedelta(days=6))
        assert result.considered_plan_ids == []
        assert result.items == []
