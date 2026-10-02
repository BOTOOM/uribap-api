from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
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
from uribap_api.infrastructure.persistence.inventory_models import InventoryLot, InventoryMovement
from uribap_api.infrastructure.persistence.planning_models import MealPlan, MealPlanEntry
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeVersion,
    RecipeVersionIngredient,
)
from uribap_api.main import app

pytestmark = pytest.mark.integration

WEEK = date(2030, 1, 7) + timedelta(weeks=int(uuid4().int % 200))


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
    *,
    state: MealPlanState = MealPlanState.APPROVED,
    position: int = 0,
) -> tuple[MealPlan, MealPlanEntry, Ingredient, InventoryLot]:
    recipe_id, version_id, plan_id = uuid4(), uuid4(), uuid4()
    ingredient = Ingredient(
        id=uuid4(),
        household_id=household.id,
        name=f"Rice {uuid4()}",
        normalized_name=f"rice-{uuid4()}",
        dimension=IngredientDimension.MASS,
        base_unit="g",
    )
    recipe = Recipe(
        id=recipe_id,
        household_id=household.id,
        name=f"Meal {uuid4()}",
        normalized_name=f"meal-{uuid4()}",
        created_by_user_id=member.user_id,
    )
    version = RecipeVersion(
        id=version_id,
        recipe_id=recipe_id,
        version_number=1,
        base_servings=2,
        prep_minutes=15,
        state=RecipeVersionState.PUBLISHED,
        created_by_user_id=member.user_id,
        published_by_user_id=member.user_id,
    )
    plan = MealPlan(
        id=plan_id,
        household_id=household.id,
        week_start_date=week,
        state=state,
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
        servings=2,
        position=position,
        added_by_user_id=member.user_id,
    )
    session.add(
        RecipeVersionIngredient(
            recipe_version_id=version.id,
            ingredient_id=ingredient.id,
            amount=Decimal("100"),
            unit="g",
            position=0,
            optional=False,
        )
    )
    lot = InventoryLot(
        household_id=household.id,
        ingredient_id=ingredient.id,
        quantity_on_hand=Decimal("500"),
        unit="g",
        location=InventoryLocation.PANTRY,
        available=True,
        created_by_user_id=member.user_id,
    )
    session.add_all([entry, lot])
    session.flush()
    return plan, entry, ingredient, lot


def test_skip_route_records_without_inventory_and_enforces_conflicts(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    household, member = _member(session, "Skip route")
    plan, entry, _ingredient, lot = _entry(session, household, member, WEEK)
    draft_plan, draft_entry, _draft_ingredient, _draft_lot = _entry(
        session, household, member, WEEK + timedelta(weeks=1), state=MealPlanState.DRAFT
    )
    other_household, other_member = _member(session, "Other skip route")
    foreign_plan, foreign_entry, _foreign_ingredient, _foreign_lot = _entry(
        session, other_household, other_member, WEEK
    )
    mismatched_plan, mismatched_entry, _mismatch_ingredient, _mismatch_lot = _entry(
        session, household, member, WEEK + timedelta(weeks=2)
    )
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)

    try:
        with TestClient(app) as client:
            url = f"/api/v1/plans/{plan.id}/entries/{entry.id}/skip"
            response = client.post(
                url,
                json={"reason": "delivery"},
                headers={"Idempotency-Key": "skip-route-replay"},
            )
            assert response.status_code == 201
            payload = response.json()
            assert payload["state"] == "recorded"
            assert payload["outcome"] == "skipped"
            assert payload["outcome_note"] == "delivery"
            assert payload["lines"] == []

            replay = client.post(
                url,
                json={"reason": "delivery"},
                headers={"Idempotency-Key": "skip-route-replay"},
            )
            assert replay.status_code == 201
            assert replay.json() == payload

            changed_fingerprint = client.post(
                url,
                json={"reason": "ate out"},
                headers={"Idempotency-Key": "skip-route-replay"},
            )
            assert changed_fingerprint.status_code == 409

            duplicate = client.post(
                url,
                json={"reason": "delivery"},
                headers={"Idempotency-Key": "skip-route-new-key"},
            )
            assert duplicate.status_code == 409
            assert duplicate.json()["detail"] == "The entry already has a recorded completion."

            too_long = client.post(url, json={"reason": "x" * 2001})
            assert too_long.status_code == 422

            non_approved = client.post(
                f"/api/v1/plans/{draft_plan.id}/entries/{draft_entry.id}/skip",
                json={},
            )
            assert non_approved.status_code == 409

            foreign = client.post(
                f"/api/v1/plans/{foreign_plan.id}/entries/{foreign_entry.id}/skip",
                json={},
            )
            assert foreign.status_code == 404

            mismatched = client.post(
                f"/api/v1/plans/{plan.id}/entries/{mismatched_entry.id}/skip",
                json={},
            )
            assert mismatched.status_code == 404

        session.refresh(lot)
        assert lot.quantity_on_hand == Decimal("500.000000")
        assert (
            session.scalar(
                select(func.count())
                .select_from(InventoryMovement)
                .where(InventoryMovement.lot_id == lot.id)
            )
            == 0
        )
        assert mismatched_plan.id != plan.id
    finally:
        session.close()


def test_skip_route_requires_authentication() -> None:
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/plans/{uuid4()}/entries/{uuid4()}/skip",
            json={},
        )
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
