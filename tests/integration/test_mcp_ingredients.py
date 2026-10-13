from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.main import app
from uribap_api.mcp import tokens

pytestmark = pytest.mark.integration

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


@pytest.fixture
def mcp_ingredient_token(integration_engine) -> str:
    user_id, household_id = uuid4(), uuid4()
    with Session(integration_engine) as session:
        session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
        session.add(Household(id=household_id, name="MCP ingredients", locale="es", timezone="UTC"))
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


def _call(client: TestClient, token: str, name: str, arguments: dict, request_id: int):
    response = client.post(
        "/api/v1/mcp",
        json={
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return response.json()["result"]


def test_mcp_ingredient_tools_create_update_and_list_pantry_staples(
    mcp_ingredient_token: str,
) -> None:
    name = f"Olive oil {uuid4()}"

    with TestClient(app) as client:
        listed_tools = client.post(
            "/api/v1/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={**MCP_HEADERS, "Authorization": f"Bearer {mcp_ingredient_token}"},
        )
        assert listed_tools.status_code == 200
        tools = {tool["name"]: tool for tool in listed_tools.json()["result"]["tools"]}
        expected_description = (
            "Pantry staples are not consumed when cooking and appear in shopping only after stock "
            "runs out."
        )
        assert expected_description in tools["uribap_create_ingredient"]["description"]
        assert expected_description in tools["uribap_update_ingredient"]["description"]

        created = _call(
            client,
            mcp_ingredient_token,
            "uribap_create_ingredient",
            {
                "name": name,
                "dimension": "volume",
                "base_unit": "ml",
                "pantry_staple": True,
            },
            2,
        )
        assert created["isError"] is False
        ingredient_id = created["structuredContent"]["id"]
        assert created["structuredContent"]["pantry_staple"] is True

        updated = _call(
            client,
            mcp_ingredient_token,
            "uribap_update_ingredient",
            {"ingredient_id": ingredient_id, "pantry_staple": False},
            3,
        )
        assert updated["isError"] is False
        assert updated["structuredContent"]["pantry_staple"] is False

        listed = _call(
            client,
            mcp_ingredient_token,
            "uribap_list_ingredients",
            {"query": name},
            4,
        )

    assert listed["isError"] is False
    assert listed["structuredContent"]["count"] == 1
    assert listed["structuredContent"]["items"][0]["pantry_staple"] is False


def test_mcp_ingredient_listing_continues_with_filters_and_preserves_fields(
    mcp_ingredient_token: str,
) -> None:
    prefix = f"mcp-pagination-{uuid4().hex}"
    ingredient_ids = set()

    with TestClient(app) as client:
        for suffix in ("a", "b", "c"):
            created = _call(
                client,
                mcp_ingredient_token,
                "uribap_create_ingredient",
                {
                    "name": f"{prefix}-{suffix}",
                    "dimension": "mass",
                    "base_unit": "g",
                },
                len(ingredient_ids) + 2,
            )
            assert created["isError"] is False
            ingredient_ids.add(created["structuredContent"]["id"])

        filters = {
            "query": prefix,
            "dimension": "mass",
            "include_global": False,
            "limit": 2,
        }
        first_page = _call(
            client,
            mcp_ingredient_token,
            "uribap_list_ingredients",
            filters,
            5,
        )
        assert first_page["isError"] is False
        first_payload = first_page["structuredContent"]
        assert first_payload["count"] == 2
        assert len(first_payload["items"]) == 2
        assert first_payload["next_cursor"] is not None

        second_page = _call(
            client,
            mcp_ingredient_token,
            "uribap_list_ingredients",
            {**filters, "cursor": first_payload["next_cursor"]},
            6,
        )

    assert second_page["isError"] is False
    second_payload = second_page["structuredContent"]
    assert second_payload["count"] == 1
    assert len(second_payload["items"]) == 1
    assert second_payload["next_cursor"] is None
    actual_ids = {item["id"] for item in first_payload["items"] + second_payload["items"]}
    assert actual_ids == ingredient_ids
