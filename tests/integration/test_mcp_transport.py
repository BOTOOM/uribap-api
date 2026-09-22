from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.main import app
from uribap_api.mcp import tokens

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _rpc(client: TestClient, token: str | None, payload: dict):
    headers = dict(MCP_HEADERS)
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return client.post("/api/v1/mcp", json=payload, headers=headers)


def _initialize(client: TestClient, token: str | None):
    return _rpc(
        client,
        token,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0"},
            },
        },
    )


@pytest.fixture
def mcp_token(integration_engine) -> str:
    user_id = uuid4()
    household_id = uuid4()
    with Session(integration_engine) as session:
        session.add(
            AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True)
        )
        session.add(
            Household(id=household_id, name="MCP", locale="es", timezone="UTC")
        )
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


@pytest.mark.integration
def test_mcp_endpoint_requires_bearer_token(mcp_token: str) -> None:
    with TestClient(app) as client:
        missing = _initialize(client, None)
        wrong_scheme = client.post(
            "/api/v1/mcp",
            content="{}",
            headers={**MCP_HEADERS, "Authorization": "Basic abc"},
        )
        garbage = _initialize(client, "uribap_mcp_garbage")
    assert missing.status_code == 401
    assert wrong_scheme.status_code == 401
    assert garbage.status_code == 401
    assert "unauthorized" in missing.json()["error"]
    assert missing.headers["www-authenticate"].startswith("Bearer")


@pytest.mark.integration
def test_mcp_initialize_and_tool_call_with_valid_token(mcp_token: str) -> None:
    with TestClient(app) as client:
        init = _initialize(client, mcp_token)
        assert init.status_code == 200
        result = init.json()["result"]
        assert result["serverInfo"]["name"] == "uribap"
        assert "tools" in result["capabilities"]

        listing = _rpc(
            client,
            mcp_token,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        assert listing.status_code == 200
        names = {tool["name"] for tool in listing.json()["result"]["tools"]}
        assert "uribap_get_context" in names
        assert "uribap_get_inventory" in names
        assert "uribap_add_plan_entry" in names

        call = _rpc(
            client,
            mcp_token,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "uribap_get_context", "arguments": {}},
            },
        )
        assert call.status_code == 200
        tool_result = call.json()["result"]
        assert tool_result["isError"] is False
        context = tool_result["structuredContent"]
        assert context["household"]["name"] == "MCP"


@pytest.mark.integration
def test_mcp_tool_call_returns_structured_error_for_bad_input(mcp_token: str) -> None:
    with TestClient(app) as client:
        call = _rpc(
            client,
            mcp_token,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "uribap_list_movements",
                    "arguments": {"lot_id": "not-a-uuid"},
                },
            },
        )
        assert call.status_code == 200
        assert call.json()["result"]["isError"] is True
