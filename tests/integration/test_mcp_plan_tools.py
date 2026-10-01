from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from uribap_api.mcp import tokens

pytestmark = pytest.mark.integration

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
WEEK = date(2032, 1, 5) + timedelta(weeks=int(uuid4().int % 200))
SKIP_DESCRIPTION = (
    "Record that a planned meal was not cooked at home (delivery, ate out, skipped). "
    "Removes it from forecast and shopping demand without touching inventory. "
    "Reopen the completion to undo."
)


@pytest.fixture
def plan_entry_context(integration_engine) -> dict[str, str]:
    user_id, household_id = uuid4(), uuid4()
    ingredient_id, recipe_id, version_id, plan_id, entry_id = (
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
        uuid4(),
    )
    with Session(integration_engine) as session:
        session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
        household = Household(id=household_id, name="MCP plan tools", locale="es", timezone="UTC")
        member = HouseholdMember(
            household_id=household_id,
            user_id=user_id,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        ingredient = Ingredient(
            id=ingredient_id,
            household_id=household_id,
            name=f"Rice {uuid4()}",
            normalized_name=f"rice-{uuid4()}",
            dimension=IngredientDimension.MASS,
            base_unit="g",
        )
        recipe = Recipe(
            id=recipe_id,
            household_id=household_id,
            name=f"MCP meal {uuid4()}",
            normalized_name=f"mcp-meal-{uuid4()}",
            description="A quick meal for the week.",
            created_by_user_id=user_id,
        )
        version = RecipeVersion(
            id=version_id,
            recipe_id=recipe_id,
            version_number=1,
            base_servings=2,
            prep_minutes=20,
            state=RecipeVersionState.PUBLISHED,
            created_by_user_id=user_id,
            published_by_user_id=user_id,
        )
        plan = MealPlan(
            id=plan_id,
            household_id=household_id,
            week_start_date=WEEK,
            state=MealPlanState.APPROVED,
            version=1,
            created_by_user_id=user_id,
        )
        entry = MealPlanEntry(
            id=entry_id,
            household_id=household_id,
            meal_plan_id=plan_id,
            planned_date=WEEK,
            meal_type=RecipeMealType.DINNER,
            recipe_version_id=version_id,
            servings=4,
            position=0,
            added_by_user_id=user_id,
        )
        lot = InventoryLot(
            household_id=household_id,
            ingredient_id=ingredient_id,
            quantity_on_hand=Decimal("50"),
            unit="g",
            location=InventoryLocation.PANTRY,
            available=True,
            created_by_user_id=user_id,
        )
        unavailable = InventoryLot(
            household_id=household_id,
            ingredient_id=ingredient_id,
            quantity_on_hand=Decimal("500"),
            unit="g",
            location=InventoryLocation.PANTRY,
            available=False,
            created_by_user_id=user_id,
        )
        session.add_all([household, member, ingredient, recipe, version, plan])
        session.flush()
        session.add_all(
            [
                entry,
                lot,
                unavailable,
                RecipeVersionIngredient(
                    recipe_version_id=version_id,
                    ingredient_id=ingredient_id,
                    amount=Decimal("100"),
                    unit="g",
                    position=0,
                    optional=False,
                ),
            ]
        )
        session.flush()
        _, token = tokens.create_token(session, member, "pytest")
        session.commit()
        return {
            "token": token,
            "plan_id": str(plan_id),
            "entry_id": str(entry_id),
            "lot_id": str(lot.id),
        }


def _rpc(client: TestClient, token: str, payload: dict):
    return client.post(
        "/api/v1/mcp",
        json=payload,
        headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
    )


def _call(
    client: TestClient,
    token: str,
    name: str,
    arguments: dict,
    request_id: int,
) -> dict:
    response = _rpc(
        client,
        token,
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )
    assert response.status_code == 200
    return response.json()["result"]


def test_plan_tool_list_exposes_skip_and_entry_detail_metadata(
    plan_entry_context: dict[str, str],
) -> None:
    with TestClient(app) as client:
        response = _rpc(
            client,
            plan_entry_context["token"],
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert response.status_code == 200
    tools_by_name = {tool["name"]: tool for tool in response.json()["result"]["tools"]}
    skip = tools_by_name["uribap_skip_meal"]
    assert skip["description"] == SKIP_DESCRIPTION
    assert skip["annotations"]["title"] == "Mark meal as not cooked"
    assert skip["annotations"]["readOnlyHint"] is False
    detail = tools_by_name["uribap_get_plan_entry"]
    assert detail["annotations"]["title"] == "Plan entry detail"
    assert detail["annotations"]["readOnlyHint"] is True
    assert "uribap_complete_meal" in tools_by_name
    assert "forecast" in tools_by_name["uribap_complete_meal"]["description"].lower()
    assert "shopping demand" in tools_by_name["uribap_complete_meal"]["description"].lower()


def test_mcp_skip_meal_records_skipped_outcome_without_inventory(
    plan_entry_context: dict[str, str],
    integration_engine,
) -> None:
    with TestClient(app) as client:
        result = _call(
            client,
            plan_entry_context["token"],
            "uribap_skip_meal",
            {
                "plan_id": plan_entry_context["plan_id"],
                "entry_id": plan_entry_context["entry_id"],
                "reason": "ate out",
                "idempotency_key": "mcp-skip-meal",
            },
            2,
        )
    assert result["isError"] is False
    payload = result["structuredContent"]
    assert payload["outcome"] == "skipped"
    assert payload["outcome_note"] == "ate out"
    assert payload["lines"] == []
    with Session(integration_engine) as session:
        lot = session.get(InventoryLot, UUID(plan_entry_context["lot_id"]))
        assert lot is not None
        assert lot.quantity_on_hand == Decimal("50.000000")
        assert (
            session.scalar(select(InventoryMovement).where(InventoryMovement.lot_id == lot.id))
            is None
        )


def test_mcp_get_plan_entry_returns_detail_payload(
    plan_entry_context: dict[str, str],
) -> None:
    with TestClient(app) as client:
        result = _call(
            client,
            plan_entry_context["token"],
            "uribap_get_plan_entry",
            {
                "plan_id": plan_entry_context["plan_id"],
                "entry_id": plan_entry_context["entry_id"],
            },
            3,
        )
    assert result["isError"] is False
    detail = result["structuredContent"]
    assert detail["plan_id"] == plan_entry_context["plan_id"]
    assert detail["entry_id"] == plan_entry_context["entry_id"]
    assert detail["servings"] == 4
    assert detail["prep_minutes"] == 20
    assert detail["completion"] is None
    assert Decimal(detail["ingredients"][0]["required_amount"]) == Decimal("200")
    assert Decimal(detail["ingredients"][0]["on_hand_amount"]) == Decimal("50")
    assert Decimal(detail["ingredients"][0]["shortfall_amount"]) == Decimal("150")
