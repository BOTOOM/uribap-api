from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from uribap_api.api.completion_schemas import MealCompletionCreate
from uribap_api.application import planning_service
from uribap_api.application.completion_service import complete_entry, reopen_completion
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.inventory.ledger import InventoryLocation
from uribap_api.domain.planning.policies import MealPlanState
from uribap_api.domain.recipes.policies import RecipeMealType, RecipeVersionState
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import InventoryLot
from uribap_api.infrastructure.persistence.planning_models import MealPlan, MealPlanEntry
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeVersion,
    RecipeVersionIngredient,
)

pytestmark = pytest.mark.integration

WEEK = date(2029, 1, 1) + timedelta(weeks=int(uuid4().int % 200))


def _member(session: Session) -> tuple[Household, HouseholdMember]:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="Detail household", locale="es", timezone="UTC"))
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


def _entry(
    session: Session,
    household: Household,
    member: HouseholdMember,
    week: date,
    name: str,
    *,
    global_ingredient_index: int | None = None,
) -> tuple[MealPlan, MealPlanEntry, list[Ingredient]]:
    recipe_id, version_id, plan_id = uuid4(), uuid4(), uuid4()
    recipe = Recipe(
        id=recipe_id,
        household_id=household.id,
        name=name,
        normalized_name=f"{name.casefold()}-{uuid4()}",
        description="Prepare a simple meal with the scaled ingredients.",
        created_by_user_id=member.user_id,
    )
    version = RecipeVersion(
        id=version_id,
        recipe_id=recipe.id,
        version_number=1,
        base_servings=2,
        prep_minutes=35,
        state=RecipeVersionState.PUBLISHED,
        created_by_user_id=member.user_id,
        published_by_user_id=member.user_id,
    )
    ingredients = [
        Ingredient(
            household_id=None if index == global_ingredient_index else household.id,
            name=f"{name} ingredient {index}",
            normalized_name=f"{name.casefold()}-{index}-{uuid4()}",
            dimension=IngredientDimension.MASS,
            base_unit=unit,
        )
        for index, unit in enumerate(("g", "ml", "g"))
    ]
    session.add_all([recipe, version, *ingredients])
    session.flush()
    session.add_all(
        [
            RecipeVersionIngredient(
                recipe_version_id=version.id,
                ingredient_id=ingredients[0].id,
                amount=Decimal("100"),
                unit="g",
                position=2,
                optional=False,
            ),
            RecipeVersionIngredient(
                recipe_version_id=version.id,
                ingredient_id=ingredients[1].id,
                amount=Decimal("25"),
                unit="ml",
                position=1,
                optional=True,
            ),
            RecipeVersionIngredient(
                recipe_version_id=version.id,
                ingredient_id=ingredients[2].id,
                amount=Decimal("10"),
                unit="g",
                position=1,
                optional=False,
            ),
        ]
    )
    plan = MealPlan(
        id=plan_id,
        household_id=household.id,
        week_start_date=week,
        state=MealPlanState.APPROVED,
        version=1,
        created_by_user_id=member.user_id,
    )
    session.add(plan)
    session.flush()
    entry = MealPlanEntry(
        household_id=household.id,
        meal_plan_id=plan.id,
        planned_date=week,
        meal_type=RecipeMealType.DINNER,
        recipe_version_id=version.id,
        servings=4,
        position=0,
        notes="Dinner with friends",
        added_by_user_id=member.user_id,
    )
    session.add(entry)
    session.flush()
    return plan, entry, ingredients


def _lot(
    session: Session,
    member: HouseholdMember,
    ingredient: Ingredient,
    amount: str,
    unit: str,
    *,
    available: bool = True,
) -> InventoryLot:
    lot = InventoryLot(
        household_id=member.household_id,
        ingredient_id=ingredient.id,
        quantity_on_hand=Decimal(amount),
        unit=unit,
        location=InventoryLocation.PANTRY,
        available=available,
        created_by_user_id=member.user_id,
    )
    session.add(lot)
    session.flush()
    return lot


def test_entry_detail_scales_orders_and_reports_available_stock(integration_engine) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session)
        plan, entry, ingredients = _entry(session, household, member, WEEK, "Detail meal")
        _lot(session, member, ingredients[0], "60", "g")
        _lot(session, member, ingredients[0], "40", "g")
        _lot(session, member, ingredients[0], "900", "g", available=False)
        _lot(session, member, ingredients[1], "60", "ml")
        session.commit()

        get_entry_detail = planning_service.get_entry_detail
        detail = get_entry_detail(session, member, plan.id, entry.id)

        assert detail.entry_id == entry.id
        assert detail.plan_id == plan.id
        assert detail.plan_state is MealPlanState.APPROVED
        assert detail.planned_date == WEEK
        assert detail.meal_type is RecipeMealType.DINNER
        assert detail.servings == 4
        assert detail.notes == "Dinner with friends"
        assert detail.recipe_name == "Detail meal"
        recipe_version = session.get(RecipeVersion, entry.recipe_version_id)
        assert recipe_version is not None
        recipe = session.get(Recipe, recipe_version.recipe_id)
        assert recipe is not None
        assert detail.recipe_id == recipe.id
        assert detail.recipe_version_id == recipe_version.id
        assert detail.recipe_description == "Prepare a simple meal with the scaled ingredients."
        assert detail.version_number == 1
        assert detail.base_servings == 2
        assert detail.prep_minutes == 35
        assert detail.completion is None
        assert [line.position for line in detail.ingredients] == [1, 1, 2]
        assert [line.ingredient_id for line in detail.ingredients[:2]] == sorted(
            line.ingredient_id for line in detail.ingredients[:2]
        )

        by_ingredient = {line.ingredient_id: line for line in detail.ingredients}
        rice = by_ingredient[ingredients[0].id]
        oil = by_ingredient[ingredients[1].id]
        beans = by_ingredient[ingredients[2].id]
        assert rice.required_amount == Decimal("200.000000")
        assert rice.on_hand_amount == Decimal("100.000000")
        assert rice.shortfall_amount == Decimal("100.000000")
        assert rice.optional is False
        assert oil.required_amount == Decimal("50.000000")
        assert oil.on_hand_amount == Decimal("60.000000")
        assert oil.shortfall_amount == Decimal("0.000000")
        assert oil.optional is True
        assert beans.required_amount == Decimal("20.000000")
        assert beans.on_hand_amount == Decimal("0.000000")
        assert beans.shortfall_amount == Decimal("20.000000")

        _lot(session, member, ingredients[0], "100", "g")
        _lot(session, member, ingredients[1], "10", "ml")
        _lot(session, member, ingredients[2], "20", "g")
        session.commit()
        created = complete_entry(session, member, plan.id, entry.id, MealCompletionCreate(), None)
        with_completion = get_entry_detail(session, member, plan.id, entry.id)
        assert with_completion.completion is not None
        assert str(with_completion.completion.id) == created.payload["id"]
        assert with_completion.completion.outcome == "cooked"

        reopen_completion(
            session,
            member,
            UUID(str(with_completion.completion.id)),
            expected_version=1,
            reason="reopened for planning",
            idempotency_key=None,
        )
        reopened = get_entry_detail(session, member, plan.id, entry.id)
        assert reopened.completion is None


def test_entry_detail_rejects_foreign_and_mismatched_plan_entries(integration_engine) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session)
        other_household, other_member = _member(session)
        plan, entry, _ingredients = _entry(session, household, member, WEEK, "Local meal")
        foreign_plan, foreign_entry, _other_ingredients = _entry(
            session, other_household, other_member, WEEK, "Foreign meal"
        )
        other_plan, other_entry, _more_ingredients = _entry(
            session, household, member, WEEK + timedelta(weeks=1), "Other local meal"
        )
        session.commit()

        get_entry_detail = planning_service.get_entry_detail
        for plan_id, entry_id in (
            (foreign_plan.id, foreign_entry.id),
            (plan.id, other_entry.id),
        ):
            with pytest.raises(DomainError) as excinfo:
                get_entry_detail(session, member, plan_id, entry_id)
            assert excinfo.value.status_code == 404
        assert other_plan.id != plan.id


def test_entry_detail_includes_global_ingredient_name(integration_engine) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session)
        plan, entry, ingredients = _entry(
            session,
            household,
            member,
            WEEK,
            "Global ingredient meal",
            global_ingredient_index=1,
        )
        session.commit()

        detail = planning_service.get_entry_detail(session, member, plan.id, entry.id)

        global_ingredient = ingredients[1]
        line = next(
            line for line in detail.ingredients if line.ingredient_id == global_ingredient.id
        )
        assert line.ingredient_name == global_ingredient.name


def test_entry_detail_allows_recipe_version_without_ingredients(integration_engine) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session)
        plan, entry, _ingredients = _entry(session, household, member, WEEK, "Empty recipe")
        session.execute(
            delete(RecipeVersionIngredient).where(
                RecipeVersionIngredient.recipe_version_id == entry.recipe_version_id
            )
        )
        session.commit()

        detail = planning_service.get_entry_detail(session, member, plan.id, entry.id)

        assert detail.recipe_description == "Prepare a simple meal with the scaled ingredients."
        assert detail.ingredients == []
