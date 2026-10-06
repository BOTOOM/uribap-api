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
