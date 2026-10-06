from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.inventory.ledger import InventoryLocation
from uribap_api.domain.planning.policies import MealPlanState
from uribap_api.domain.recipes.policies import RecipeMealType, RecipeVersionState
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
from uribap_api.main import app

pytestmark = pytest.mark.integration

WEEK = date(2031, 1, 6) + timedelta(weeks=int(uuid4().int % 200))


def _member(session: Session, name: str) -> tuple[Household, HouseholdMember]:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name=name, locale="es", timezone="UTC"))
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
) -> tuple[MealPlan, MealPlanEntry, Ingredient]:
    recipe_id, version_id, plan_id = uuid4(), uuid4(), uuid4()
    ingredient = Ingredient(
        id=uuid4(),
        household_id=household.id,
        name=f"{name} ingredient",
        normalized_name=f"{name.casefold()}-{uuid4()}",
        dimension=IngredientDimension.MASS,
        base_unit="g",
    )
    recipe = Recipe(
        id=recipe_id,
        household_id=household.id,
        name=name,
        normalized_name=f"{name.casefold()}-{uuid4()}",
        description="A detailed recipe description.",
        created_by_user_id=member.user_id,
    )
    version = RecipeVersion(
        id=version_id,
        recipe_id=recipe_id,
        version_number=2,
        base_servings=2,
        prep_minutes=25,
        state=RecipeVersionState.PUBLISHED,
        created_by_user_id=member.user_id,
        published_by_user_id=member.user_id,
    )
    plan = MealPlan(
        id=plan_id,
        household_id=household.id,
        week_start_date=week,
        state=MealPlanState.APPROVED,
        version=1,
        created_by_user_id=member.user_id,
    )
    session.add_all([ingredient, recipe, version, plan])
    session.flush()
    entry = MealPlanEntry(
        household_id=household.id,
        meal_plan_id=plan.id,
        planned_date=week,
        meal_type=RecipeMealType.DINNER,
        recipe_version_id=version.id,
        servings=4,
        position=0,
        notes="For dinner",
        added_by_user_id=member.user_id,
    )
    session.add(
        RecipeVersionIngredient(
            recipe_version_id=version.id,
            ingredient_id=ingredient.id,
            amount=Decimal("50"),
            unit="g",
            position=0,
            optional=False,
        )
    )
    session.add_all(
        [
            entry,
            InventoryLot(
                household_id=household.id,
                ingredient_id=ingredient.id,
                quantity_on_hand=Decimal("40"),
                unit="g",
                location=InventoryLocation.PANTRY,
                available=True,
                created_by_user_id=member.user_id,
            ),
            InventoryLot(
                household_id=household.id,
                ingredient_id=ingredient.id,
                quantity_on_hand=Decimal("500"),
                unit="g",
                location=InventoryLocation.PANTRY,
                available=False,
                created_by_user_id=member.user_id,
            ),
        ]
    )
    session.flush()
    return plan, entry, ingredient


def test_plan_entry_detail_route_returns_scaled_stock_and_tenant_scoped_404s(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    household, member = _member(session, "Detail route")
    plan, entry, ingredient = _entry(session, household, member, WEEK, "Plan detail meal")
    other_plan, other_entry, _other_ingredient = _entry(
        session, household, member, WEEK + timedelta(weeks=1), "Other plan meal"
    )
    foreign_household, foreign_member = _member(session, "Foreign detail route")
    foreign_plan, foreign_entry, _foreign_ingredient = _entry(
        session, foreign_household, foreign_member, WEEK, "Foreign plan meal"
    )
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/plans/{plan.id}/entries/{entry.id}/detail")
            assert response.status_code == 200
            detail = response.json()
            assert detail["entry_id"] == str(entry.id)
            assert detail["plan_id"] == str(plan.id)
            assert detail["plan_state"] == "approved"
            assert detail["planned_date"] == WEEK.isoformat()
            assert detail["meal_type"] == "dinner"
            assert detail["servings"] == 4
            assert detail["notes"] == "For dinner"
            assert detail["recipe_name"] == "Plan detail meal"
            assert detail["recipe_description"] == "A detailed recipe description."
            assert detail["version_number"] == 2
            assert detail["base_servings"] == 2
            assert detail["prep_minutes"] == 25
            assert detail["completion"] is None
            assert detail["ingredients"] == [
                {
                    "ingredient_id": str(ingredient.id),
                    "ingredient_name": "Plan detail meal ingredient",
                    "required_amount": "100.000000",
                    "unit": "g",
                    "optional": False,
                    "on_hand_amount": "40.000000",
                    "shortfall_amount": "60.000000",
                    "position": 0,
                    "pantry_staple": False,
                }
            ]

            foreign = client.get(
                f"/api/v1/plans/{foreign_plan.id}/entries/{foreign_entry.id}/detail"
            )
            assert foreign.status_code == 404
            mismatched = client.get(f"/api/v1/plans/{plan.id}/entries/{other_entry.id}/detail")
            assert mismatched.status_code == 404
        assert other_plan.id != plan.id
    finally:
        session.close()


def test_plan_entry_detail_route_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/plans/{uuid4()}/entries/{uuid4()}/detail")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_plan_entry_detail_route_includes_pantry_staple_status(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    household, member = _member(session, "Pantry detail route")
    plan, entry, ingredient = _entry(session, household, member, WEEK, "Pantry detail")
    ingredient.pantry_staple = True
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)

    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/plans/{plan.id}/entries/{entry.id}/detail")

        assert response.status_code == 200
        line = response.json()["ingredients"][0]
        assert line["ingredient_id"] == str(ingredient.id)
        assert line["pantry_staple"] is True
        assert line["on_hand_amount"] == "40.000000"
        assert Decimal(line["shortfall_amount"]) == Decimal("0")
    finally:
        session.close()
