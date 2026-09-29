from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension, normalize_ingredient_name
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.recipe_models import Recipe
from uribap_api.main import app
from uribap_api.mcp import tokens

pytestmark = pytest.mark.integration

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


@pytest.fixture
def mcp_recipe_token(integration_engine) -> str:
    user_id, household_id = uuid4(), uuid4()
    with Session(integration_engine) as session:
        session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
        session.add(Household(id=household_id, name="MCP recipes", locale="es", timezone="UTC"))
        member = HouseholdMember(
            household_id=household_id,
            user_id=user_id,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        session.add(member)
        session.commit()
        _, plaintext = tokens.create_token(session, member, "pytest")
    return plaintext


def _rpc(client: TestClient, token: str, payload: dict):
    return client.post(
        "/api/v1/mcp",
        json=payload,
        headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
    )


def _call(client: TestClient, token: str, name: str, arguments: dict, request_id: int):
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


def test_mcp_recipe_lifecycle_tools_and_member_list(mcp_recipe_token: str) -> None:
    with TestClient(app) as client:
        listing = _rpc(
            client,
            mcp_recipe_token,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        names = {tool["name"] for tool in listing.json()["result"]["tools"]}
        assert {
            "uribap_update_recipe",
            "uribap_archive_recipe",
            "uribap_unarchive_recipe",
        }.issubset(names)

        members = _call(client, mcp_recipe_token, "uribap_list_members", {}, 2)
        assert members["isError"] is False
        assert members["structuredContent"]["count"] == 1
        assert len(members["structuredContent"]["items"]) == 1

        recipe_name = f"Lifecycle {uuid4()}"
        created = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {
                "name": recipe_name,
                "ingredients": [
                    {"ingredient_name": f"Rice {uuid4()}", "amount": "100", "unit": "g"}
                ],
            },
            3,
        )
        assert created["isError"] is False
        recipe_id = created["structuredContent"]["recipe_id"]

        updated = _call(
            client,
            mcp_recipe_token,
            "uribap_update_recipe",
            {
                "recipe_id": recipe_id,
                "ingredients": [
                    {"ingredient_name": created["structuredContent"]["auto_created_ingredients"][0],
                     "amount": "150",
                     "unit": "g"}
                ],
            },
            4,
        )
        assert updated["isError"] is False
        assert updated["structuredContent"]["version_number"] == 2
        assert updated["structuredContent"]["state"] == "published"

        detail = _call(
            client,
            mcp_recipe_token,
            "uribap_get_recipe",
            {"recipe_name": recipe_name},
            5,
        )
        assert detail["isError"] is False
        assert detail["structuredContent"]["active_version"]["version_number"] == 2
        assert detail["structuredContent"]["ingredients_version_number"] == 2
        assert detail["structuredContent"]["ingredients"][0]["amount"] == "150"

        archived = _call(
            client, mcp_recipe_token, "uribap_archive_recipe", {"recipe_id": recipe_id}, 6
        )
        assert archived["isError"] is False
        assert archived["structuredContent"]["archived"] is True
        listed = _call(client, mcp_recipe_token, "uribap_list_recipes", {}, 7)
        assert all(item["id"] != recipe_id for item in listed["structuredContent"]["items"])

        unarchived = _call(
            client, mcp_recipe_token, "uribap_unarchive_recipe", {"recipe_id": recipe_id}, 8
        )
        assert unarchived["isError"] is False
        assert unarchived["structuredContent"]["archived"] is False


def test_mcp_create_recipe_validates_all_lines_before_writing(mcp_recipe_token: str) -> None:
    recipe_name = f"Invalid lines {uuid4()}"
    auto_name = f"Should not exist {uuid4()}"
    with TestClient(app) as client:
        result = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {
                "name": recipe_name,
                "ingredients": [
                    {"ingredient_name": auto_name, "amount": "100", "unit": "g"},
                    {"ingredient_name": f"Unknown unit {uuid4()}", "amount": "1", "unit": "cup"},
                ],
            },
            1,
        )
        assert result["isError"] is True

        recipes = _call(client, mcp_recipe_token, "uribap_list_recipes", {}, 2)
        assert all(item["name"] != recipe_name for item in recipes["structuredContent"]["items"])
        ingredients = _call(
            client, mcp_recipe_token, "uribap_list_ingredients", {"query": auto_name}, 3
        )
        assert ingredients["structuredContent"]["count"] == 0


def test_mcp_create_recipe_rejects_out_of_range_amount_without_writes(
    mcp_recipe_token: str,
    integration_engine,
) -> None:
    recipe_name = f"Out of range {uuid4()}"
    ingredient_name = f"Unpersisted ingredient {uuid4()}"

    with TestClient(app) as client:
        result = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {
                "name": recipe_name,
                "ingredients": [
                    {
                        "ingredient_name": ingredient_name,
                        "amount": "1000000000000",
                        "unit": "g",
                    }
                ],
            },
            1,
        )

    assert result["isError"] is True
    with Session(integration_engine) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(Recipe).where(Recipe.name == recipe_name)
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Ingredient)
                .where(Ingredient.name == ingredient_name)
            )
            == 0
        )


def test_mcp_update_recipe_validates_metadata_before_revising(
    mcp_recipe_token: str,
    integration_engine,
) -> None:
    ingredient_name = f"Unpersisted update ingredient {uuid4()}"
    with TestClient(app) as client:
        created = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {"name": f"Update validation {uuid4()}", "ingredients": []},
            1,
        )
        recipe_id = created["structuredContent"]["recipe_id"]
        result = _call(
            client,
            mcp_recipe_token,
            "uribap_update_recipe",
            {
                "recipe_id": recipe_id,
                "name": "   ",
                "base_servings": 6,
                "ingredients": [
                    {
                        "ingredient_name": ingredient_name,
                        "amount": "10",
                        "unit": "g",
                    }
                ],
            },
            2,
        )
        detail = _call(
            client, mcp_recipe_token, "uribap_get_recipe", {"recipe_id": recipe_id}, 3
        )

    assert result["isError"] is True
    assert [
        version["version_number"] for version in detail["structuredContent"]["versions"]
    ] == [1]
    with Session(integration_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Ingredient)
                .where(Ingredient.name == ingredient_name)
            )
            == 0
        )


def test_mcp_create_recipe_rejects_duplicate_active_name(mcp_recipe_token: str) -> None:
    name = f"Duplicate {uuid4()}"
    with TestClient(app) as client:
        first = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {"name": name, "ingredients": []},
            1,
        )
        second = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {"name": f" {name.upper()} ", "ingredients": []},
            2,
        )

    assert first["isError"] is False
    assert second["isError"] is True
    assert "uribap_update_recipe" in second["content"][0]["text"]


def test_mcp_register_purchase_by_name_creates_then_reuses_ingredient(
    mcp_recipe_token: str,
) -> None:
    ingredient_name = f"Purchase ingredient {uuid4()}"
    arguments = {
        "ingredient_name": ingredient_name,
        "quantity": "500",
        "unit": "g",
        "location": "pantry",
    }
    with TestClient(app) as client:
        first = _call(client, mcp_recipe_token, "uribap_register_purchase", arguments, 1)
        second = _call(client, mcp_recipe_token, "uribap_register_purchase", arguments, 2)

    assert first["isError"] is False
    assert second["isError"] is False
    assert first["structuredContent"]["auto_created_ingredient"] is True
    assert second["structuredContent"]["auto_created_ingredient"] is False
    assert (
        first["structuredContent"]["ingredient_id"]
        == second["structuredContent"]["ingredient_id"]
    )


def test_mcp_purchase_rejects_rounded_zero_without_creating_ingredient(
    mcp_recipe_token: str,
    integration_engine,
) -> None:
    ingredient_name = f"Rounded zero {uuid4()}"

    with TestClient(app) as client:
        result = _call(
            client,
            mcp_recipe_token,
            "uribap_register_purchase",
            {
                "ingredient_name": ingredient_name,
                "quantity": "0.0000001",
                "unit": "g",
                "location": "pantry",
            },
            1,
        )

    assert result["isError"] is True
    with Session(integration_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Ingredient)
                .where(Ingredient.name == ingredient_name)
            )
            == 0
        )


def test_mcp_exact_ingredient_lookup_finds_match_after_100_substring_results(
    mcp_recipe_token: str,
    integration_engine,
) -> None:
    target_name = f"Zucchini {uuid4()}"
    candidates = [
        Ingredient(
            household_id=None,
            name=f"A {index:03d} {target_name}",
            normalized_name=normalize_ingredient_name(f"A {index:03d} {target_name}"),
            dimension=IngredientDimension.MASS,
            base_unit="g",
        )
        for index in range(100)
    ]
    target = Ingredient(
        household_id=None,
        name=target_name,
        normalized_name=normalize_ingredient_name(target_name),
        dimension=IngredientDimension.MASS,
        base_unit="g",
    )
    with Session(integration_engine) as session:
        session.add_all([*candidates, target])
        session.commit()
        target_id = target.id

    with TestClient(app) as client:
        recipe = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {
                "name": f"Exact lookup {uuid4()}",
                "ingredients": [
                    {"ingredient_name": target_name, "amount": "20", "unit": "g"}
                ],
            },
            1,
        )
        detail = _call(
            client,
            mcp_recipe_token,
            "uribap_get_recipe",
            {"recipe_id": recipe["structuredContent"]["recipe_id"]},
            2,
        )
        purchase = _call(
            client,
            mcp_recipe_token,
            "uribap_register_purchase",
            {
                "ingredient_name": target_name,
                "quantity": "500",
                "unit": "g",
                "location": "pantry",
            },
            3,
        )

    assert recipe["isError"] is False
    assert recipe["structuredContent"]["auto_created_ingredients"] == []
    assert detail["structuredContent"]["ingredients"][0]["ingredient_id"] == str(target_id)
    assert purchase["isError"] is False
    assert purchase["structuredContent"]["auto_created_ingredient"] is False
    assert purchase["structuredContent"]["ingredient_id"] == str(target_id)


def test_mcp_get_recipe_by_name_prefers_active_match(
    mcp_recipe_token: str,
) -> None:
    recipe_name = f"Archived and active {uuid4()}"
    with TestClient(app) as client:
        archived = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {"name": recipe_name, "ingredients": []},
            1,
        )
        archived_id = archived["structuredContent"]["recipe_id"]
        _call(
            client,
            mcp_recipe_token,
            "uribap_archive_recipe",
            {"recipe_id": archived_id},
            2,
        )
        active = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {"name": recipe_name, "ingredients": []},
            3,
        )
        detail = _call(
            client,
            mcp_recipe_token,
            "uribap_get_recipe",
            {"recipe_name": recipe_name},
            4,
        )

    assert detail["isError"] is False
    assert detail["structuredContent"]["id"] == active["structuredContent"]["recipe_id"]
    assert detail["structuredContent"]["archived"] is False


def test_mcp_get_recipe_by_name_reports_ambiguous_matches(
    mcp_recipe_token: str,
) -> None:
    recipe_name = f"Ambiguous recipe {uuid4()}"
    with TestClient(app) as client:
        first = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {"name": recipe_name, "ingredients": []},
            1,
        )
        second = _call(
            client,
            mcp_recipe_token,
            "uribap_create_recipe",
            {"name": f"Other recipe {uuid4()}", "ingredients": []},
            2,
        )
        first_id = first["structuredContent"]["recipe_id"]
        second_id = second["structuredContent"]["recipe_id"]
        _call(
            client,
            mcp_recipe_token,
            "uribap_update_recipe",
            {"recipe_id": second_id, "name": recipe_name},
            3,
        )
        active_ambiguity = _call(
            client,
            mcp_recipe_token,
            "uribap_get_recipe",
            {"recipe_name": recipe_name},
            4,
        )
        _call(
            client,
            mcp_recipe_token,
            "uribap_archive_recipe",
            {"recipe_id": first_id},
            5,
        )
        _call(
            client,
            mcp_recipe_token,
            "uribap_archive_recipe",
            {"recipe_id": second_id},
            6,
        )
        archived_ambiguity = _call(
            client,
            mcp_recipe_token,
            "uribap_get_recipe",
            {"recipe_name": recipe_name},
            7,
        )

    for ambiguity in (active_ambiguity, archived_ambiguity):
        assert ambiguity["isError"] is True
        error = ambiguity["content"][0]["text"]
        assert first_id in error
        assert second_id in error
