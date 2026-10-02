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
GET_MEMORY_DESCRIPTION = (
    "Read what the household remembers: each diner's likes, dislikes, restrictions and goals plus "
    "household-wide notes. Read this before suggesting or planning meals and respect restrictions."
)
CONTEXT_MEMORY_SENTENCE = (
    "Includes the household memory (diners' likes, dislikes, restrictions, "
    "goals and household notes)."
)


@pytest.fixture
def memory_mcp_context(integration_engine) -> dict[str, str]:
    user_id, household_id = uuid4(), uuid4()
    with Session(integration_engine) as session:
        session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
        session.add(Household(id=household_id, name="MCP memory", locale="es", timezone="UTC"))
        member = HouseholdMember(
            household_id=household_id,
            user_id=user_id,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        session.add(member)
        session.commit()
        _, token = tokens.create_token(session, member, "pytest")
    return {
        "token": token,
        "household_id": str(household_id),
        "user_id": str(user_id),
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


def _error_text(result: dict) -> str:
    return " ".join(part.get("text", "") for part in result.get("content", []))


def test_memory_tools_are_registered_with_required_annotations_and_descriptions(
    memory_mcp_context: dict[str, str],
) -> None:
    with TestClient(app) as client:
        response = _rpc(
            client,
            memory_mcp_context["token"],
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.json()["result"]["tools"]}
    expected_write_tools = {
        "uribap_add_diner",
        "uribap_update_diner",
        "uribap_archive_diner",
        "uribap_remember",
        "uribap_update_memory",
        "uribap_forget_memory",
    }
    assert expected_write_tools.issubset(tools)
    assert tools["uribap_get_memory"]["description"] == GET_MEMORY_DESCRIPTION
    assert tools["uribap_get_memory"]["annotations"]["readOnlyHint"] is True
    assert all(tools[name]["annotations"]["readOnlyHint"] is False for name in expected_write_tools)
    assert CONTEXT_MEMORY_SENTENCE in tools["uribap_get_context"]["description"]
    assert "unlink_member=true" in tools["uribap_update_diner"]["description"]


def test_memory_tools_resolve_names_update_current_versions_and_archive(
    memory_mcp_context: dict[str, str],
) -> None:
    token = memory_mcp_context["token"]
    with TestClient(app) as client:
        context = _call(client, token, "uribap_get_context", {}, 2)
        assert context["isError"] is False
        assert "memory" in context["structuredContent"]

        added = _call(
            client,
            token,
            "uribap_add_diner",
            {"display_name": "Mina", "idempotency_key": "mcp-diner-retry"},
            3,
        )
        assert added["isError"] is False
        diner = added["structuredContent"]
        assert diner["display_name"] == "Mina"
        assert diner["version"] == 1

        added_retry = _call(
            client,
            token,
            "uribap_add_diner",
            {"display_name": "Mina", "idempotency_key": "mcp-diner-retry"},
            16,
        )
        assert added_retry["structuredContent"] == diner

        linked_diner = _call(
            client,
            token,
            "uribap_update_diner",
            {
                "diner_id": diner["id"],
                "member_user_id": memory_mcp_context["user_id"],
            },
            17,
        )
        assert linked_diner["structuredContent"]["member_user_id"] == memory_mcp_context["user_id"]

        updated_diner = _call(
            client,
            token,
            "uribap_update_diner",
            {"diner_id": diner["id"], "display_name": "Mina R"},
            4,
        )
        assert updated_diner["isError"] is False
        assert updated_diner["structuredContent"]["version"] == 3
        assert updated_diner["structuredContent"]["member_user_id"] == memory_mcp_context["user_id"]

        unlinked_diner = _call(
            client,
            token,
            "uribap_update_diner",
            {"diner_id": diner["id"], "unlink_member": True},
            18,
        )
        assert unlinked_diner["isError"] is False
        assert unlinked_diner["structuredContent"]["member_user_id"] is None
        conflicting_unlink = _call(
            client,
            token,
            "uribap_update_diner",
            {
                "diner_id": diner["id"],
                "member_user_id": memory_mcp_context["user_id"],
                "unlink_member": True,
            },
            19,
        )
        assert conflicting_unlink["isError"] is True

        overlong_diner_key = _call(
            client,
            token,
            "uribap_add_diner",
            {"display_name": "Too long key", "idempotency_key": "x" * 129},
            20,
        )
        assert overlong_diner_key["isError"] is True

        remembered = _call(
            client,
            token,
            "uribap_remember",
            {
                "content": "Likes lentils",
                "diner_name": "mInA r",
                "idempotency_key": "mcp-memory-retry",
            },
            5,
        )
        assert remembered["isError"] is False
        memory = remembered["structuredContent"]
        assert memory["kind"] == "note"
        assert memory["diner_id"] == diner["id"]

        remembered_retry = _call(
            client,
            token,
            "uribap_remember",
            {
                "content": "Likes lentils",
                "diner_name": "mInA r",
                "idempotency_key": "mcp-memory-retry",
            },
            21,
        )
        assert remembered_retry["structuredContent"] == memory

        overlong_memory_key = _call(
            client,
            token,
            "uribap_remember",
            {"content": "Should not be saved", "idempotency_key": "x" * 129},
            22,
        )
        assert overlong_memory_key["isError"] is True

        remembered_by_id = _call(
            client,
            token,
            "uribap_remember",
            {
                "content": "Enjoys olives",
                "kind": "like",
                "diner_id": diner["id"],
            },
            6,
        )
        assert remembered_by_id["isError"] is False
        assert remembered_by_id["structuredContent"]["diner_id"] == diner["id"]

        unknown = _call(
            client,
            token,
            "uribap_remember",
            {"content": "Likes olives", "diner_name": "Unknown person"},
            7,
        )
        assert unknown["isError"] is True
        assert "create" in _error_text(unknown).casefold()
        assert "diner" in _error_text(unknown).casefold()

        both_scopes = _call(
            client,
            token,
            "uribap_remember",
            {
                "content": "Ambiguous",
                "diner_id": diner["id"],
                "diner_name": "Mina R",
            },
            8,
        )
        assert both_scopes["isError"] is True

        household_memory = _call(
            client,
            token,
            "uribap_remember",
            {"content": "Prefer seasonal produce", "kind": "goal"},
            9,
        )
        assert household_memory["isError"] is False
        household_memory_id = household_memory["structuredContent"]["id"]

        updated_memory = _call(
            client,
            token,
            "uribap_update_memory",
            {"memory_id": memory["id"], "content": "Likes lentils and rice"},
            10,
        )
        assert updated_memory["isError"] is False
        assert updated_memory["structuredContent"]["version"] == 2

        profile = _call(client, token, "uribap_get_memory", {}, 11)
        assert profile["isError"] is False
        assert [item["id"] for item in profile["structuredContent"]["household"]] == [
            household_memory_id
        ]
        assert len(profile["structuredContent"]["diners"]) == 1
        assert profile["structuredContent"]["diners"][0]["diner"]["id"] == diner["id"]
        diner_memories = {
            item["id"]: item for item in profile["structuredContent"]["diners"][0]["memories"]
        }
        assert diner_memories[memory["id"]]["content"] == "Likes lentils and rice"
        assert diner_memories[remembered_by_id["structuredContent"]["id"]]["content"] == (
            "Enjoys olives"
        )
        assert len(diner_memories) == 2
        context_after_write = _call(client, token, "uribap_get_context", {}, 12)
        assert context_after_write["structuredContent"]["memory"] == profile["structuredContent"]

        forgotten = _call(
            client,
            token,
            "uribap_forget_memory",
            {"memory_id": household_memory_id},
            13,
        )
        assert forgotten["isError"] is False

        archived_diner = _call(
            client,
            token,
            "uribap_archive_diner",
            {"diner_id": diner["id"]},
            14,
        )
        assert archived_diner["isError"] is False
        profile_after_archive = _call(client, token, "uribap_get_memory", {}, 15)
        assert profile_after_archive["structuredContent"]["diners"] == []


def test_remember_by_name_idempotency_replays_after_rename_and_name_reuse(
    memory_mcp_context: dict[str, str],
) -> None:
    token = memory_mcp_context["token"]
    with TestClient(app) as client:
        created_diner = _call(
            client,
            token,
            "uribap_add_diner",
            {"display_name": "Mina", "idempotency_key": "mina-original"},
            30,
        )["structuredContent"]
        original_memory = _call(
            client,
            token,
            "uribap_remember",
            {
                "content": "Likes lentils",
                "diner_name": "Mina",
                "idempotency_key": "k1",
            },
            31,
        )["structuredContent"]

        renamed = _call(
            client,
            token,
            "uribap_update_diner",
            {"diner_id": created_diner["id"], "display_name": "Marina"},
            32,
        )
        assert renamed["isError"] is False

        after_rename = _call(
            client,
            token,
            "uribap_remember",
            {
                "content": "Likes lentils",
                "diner_name": "Mina",
                "idempotency_key": "k1",
            },
            33,
        )
        assert after_rename["structuredContent"] == original_memory

        replacement_diner = _call(
            client,
            token,
            "uribap_add_diner",
            {"display_name": "Mina", "idempotency_key": "mina-replacement"},
            34,
        )
        assert replacement_diner["isError"] is False

        after_name_reuse = _call(
            client,
            token,
            "uribap_remember",
            {
                "content": "Likes lentils",
                "diner_name": "  mINA  ",
                "idempotency_key": "k1",
            },
            35,
        )
        assert after_name_reuse["structuredContent"] == original_memory

        content_conflict = _call(
            client,
            token,
            "uribap_remember",
            {
                "content": "Prefers pasta",
                "diner_name": "Mina",
                "idempotency_key": "k1",
            },
            36,
        )
        assert content_conflict["isError"] is True
        assert "idempotency" in _error_text(content_conflict).casefold()

        profile = _call(client, token, "uribap_get_memory", {}, 37)["structuredContent"]
        memories = [
            memory for diner_profile in profile["diners"] for memory in diner_profile["memories"]
        ]
        assert [memory["id"] for memory in memories] == [original_memory["id"]]
