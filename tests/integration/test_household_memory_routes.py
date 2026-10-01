from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def memory_route_context(integration_engine, monkeypatch) -> dict[str, str]:
    user_id, household_id = uuid4(), uuid4()
    linked_user_id = uuid4()
    with Session(integration_engine) as session:
        session.add_all(
            [
                AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True),
                AppUser(
                    id=linked_user_id,
                    email=f"{linked_user_id}@example.test",
                    email_verified=True,
                ),
                Household(
                    id=household_id,
                    name="Memory route test",
                    locale="es",
                    timezone="UTC",
                ),
            ]
        )
        member = HouseholdMember(
            household_id=household_id,
            user_id=user_id,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        linked_member = HouseholdMember(
            household_id=household_id,
            user_id=linked_user_id,
            role=MembershipRole.MEMBER,
            status=MembershipStatus.ACTIVE,
        )
        session.add_all([member, linked_member])
        session.commit()
        session.refresh(member)

    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)
    return {
        "household_id": str(household_id),
        "user_id": str(user_id),
        "linked_user_id": str(linked_user_id),
    }


def test_diner_routes_cover_create_list_patch_archive_and_error_shapes(
    memory_route_context: dict[str, str],
) -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/diners",
            json={
                "display_name": "  Alex  ",
                "member_user_id": memory_route_context["linked_user_id"],
            },
            headers={"Idempotency-Key": f"diner-route-{uuid4()}"},
        )
        assert created.status_code == 201
        diner = created.json()
        assert diner["display_name"] == "Alex"
        assert diner["member_user_id"] == memory_route_context["linked_user_id"]
        assert diner["version"] == 1

        duplicate = client.post(
            "/api/v1/diners",
            json={"display_name": "aLeX"},
            headers={"Idempotency-Key": f"diner-duplicate-{uuid4()}"},
        )
        assert duplicate.status_code == 409
        assert duplicate.json()["code"] == "conflict"

        invalid_link = client.post(
            "/api/v1/diners",
            json={"display_name": "Bad link", "member_user_id": str(uuid4())},
            headers={"Idempotency-Key": f"diner-bad-link-{uuid4()}"},
        )
        assert invalid_link.status_code == 422
        assert invalid_link.json()["code"] == "invalid_member_link"

        duplicate_member_link = client.post(
            "/api/v1/diners",
            json={
                "display_name": "Second linked diner",
                "member_user_id": memory_route_context["linked_user_id"],
            },
            headers={"Idempotency-Key": f"diner-member-conflict-{uuid4()}"},
        )
        assert duplicate_member_link.status_code == 409
        assert duplicate_member_link.json()["code"] == "invalid_member_link"

        listed = client.get("/api/v1/diners")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["items"]] == [diner["id"]]

        missing_version = client.patch(
            f"/api/v1/diners/{diner['id']}", json={"display_name": "Updated"}
        )
        assert missing_version.status_code == 422
        assert missing_version.json()["code"] == "validation_error"

        updated = client.patch(
            f"/api/v1/diners/{diner['id']}",
            json={
                "expected_version": 1,
                "display_name": "Alex updated",
                "member_user_id": None,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["display_name"] == "Alex updated"
        assert updated.json()["member_user_id"] is None
        assert updated.json()["version"] == 2

        stale = client.patch(
            f"/api/v1/diners/{diner['id']}",
            json={"expected_version": 1, "display_name": "Stale"},
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "conflict"

        foreign = client.patch(
            f"/api/v1/diners/{uuid4()}",
            json={"expected_version": 1, "display_name": "Missing"},
        )
        assert foreign.status_code == 404
        assert foreign.json()["code"] == "not_found"

        archived = client.delete(f"/api/v1/diners/{diner['id']}")
        assert archived.status_code == 204
        assert archived.content == b""
        assert client.delete(f"/api/v1/diners/{diner['id']}").status_code == 204
        assert client.get("/api/v1/diners").json()["items"] == []
        archived_list = client.get("/api/v1/diners?include_archived=true")
        assert archived_list.status_code == 200
        assert archived_list.json()["items"][0]["archived_at"] is not None


def test_memory_routes_cover_idempotency_scopes_profile_updates_and_archives(
    memory_route_context: dict[str, str],
) -> None:
    with TestClient(app) as client:
        diner_response = client.post(
            "/api/v1/diners",
            json={"display_name": "Mina"},
            headers={"Idempotency-Key": f"memory-route-diner-{uuid4()}"},
        )
        assert diner_response.status_code == 201
        diner_id = diner_response.json()["id"]

        key = f"memory-route-{uuid4()}"
        body = {
            "kind": "restriction",
            "content": "Avoid peanuts",
            "diner_id": diner_id,
        }
        created = client.post("/api/v1/memories", json=body, headers={"Idempotency-Key": key})
        assert created.status_code == 201
        memory = created.json()
        replay = client.post("/api/v1/memories", json=body, headers={"Idempotency-Key": key})
        assert replay.status_code == 201
        assert replay.json() == memory

        key_conflict = client.post(
            "/api/v1/memories",
            json={**body, "content": "Different request"},
            headers={"Idempotency-Key": key},
        )
        assert key_conflict.status_code == 409
        assert key_conflict.json()["code"] == "conflict"

        household_memory = client.post(
            "/api/v1/memories",
            json={"kind": "note", "content": "Household note"},
            headers={"Idempotency-Key": f"household-memory-{uuid4()}"},
        )
        assert household_memory.status_code == 201
        household_memory_id = household_memory.json()["id"]

        all_memories = client.get("/api/v1/memories?scope=all&limit=10")
        assert all_memories.status_code == 200
        assert len(all_memories.json()["items"]) == 2
        assert all_memories.json()["items"][0]["diner_id"] is None
        household_scope = client.get("/api/v1/memories?scope=household")
        assert [item["id"] for item in household_scope.json()["items"]] == [household_memory_id]
        diner_scope = client.get(f"/api/v1/memories?scope=diner&diner_id={diner_id}")
        assert [item["id"] for item in diner_scope.json()["items"]] == [memory["id"]]
        invalid_limit = client.get("/api/v1/memories?limit=201")
        assert invalid_limit.status_code == 422

        invalid_diner = client.post(
            "/api/v1/memories",
            json={"kind": "note", "content": "Invalid diner", "diner_id": str(uuid4())},
            headers={"Idempotency-Key": f"invalid-memory-diner-{uuid4()}"},
        )
        assert invalid_diner.status_code == 404
        assert invalid_diner.json()["code"] == "not_found"
        foreign_diner_filter = client.get(f"/api/v1/memories?diner_id={uuid4()}&scope=all")
        assert foreign_diner_filter.status_code == 404
        assert foreign_diner_filter.json()["code"] == "not_found"

        updated = client.patch(
            f"/api/v1/memories/{memory['id']}",
            json={
                "expected_version": 1,
                "content": "Updated restriction",
                "diner_id": None,
            },
        )
        assert updated.status_code == 200
        assert updated.json()["diner_id"] is None
        assert updated.json()["content"] == "Updated restriction"
        assert updated.json()["version"] == 2

        stale = client.patch(
            f"/api/v1/memories/{memory['id']}",
            json={"expected_version": 1, "kind": "note"},
        )
        assert stale.status_code == 409
        assert stale.json()["code"] == "conflict"

        missing = client.patch(
            f"/api/v1/memories/{uuid4()}",
            json={"expected_version": 1, "content": "Missing"},
        )
        assert missing.status_code == 404
        assert missing.json()["code"] == "not_found"

        profile = client.get("/api/v1/memory/profile")
        assert profile.status_code == 200
        assert {item["id"] for item in profile.json()["household"]} == {
            memory["id"],
            household_memory_id,
        }
        assert profile.json()["diners"][0]["diner"]["id"] == diner_id
        assert profile.json()["diners"][0]["memories"] == []

        archived_memory = client.delete(f"/api/v1/memories/{household_memory_id}")
        assert archived_memory.status_code == 204
        active = client.get("/api/v1/memories")
        assert household_memory_id not in {item["id"] for item in active.json()["items"]}
        archived = client.get("/api/v1/memories?include_archived=true")
        assert household_memory_id in {item["id"] for item in archived.json()["items"]}

        assert client.delete(f"/api/v1/diners/{diner_id}").status_code == 204
        assert client.get("/api/v1/memory/profile").json()["diners"] == []
        assert memory_route_context["household_id"]


def test_memory_route_authentication_problem_details() -> None:
    headers = {"X-Household-ID": str(uuid4())}
    with TestClient(app) as client:
        responses = [
            client.get("/api/v1/diners", headers=headers),
            client.post("/api/v1/diners", json={"display_name": "Alex"}, headers=headers),
            client.patch(
                f"/api/v1/diners/{uuid4()}",
                json={"expected_version": 1, "display_name": "Alex"},
                headers=headers,
            ),
            client.delete(f"/api/v1/diners/{uuid4()}", headers=headers),
            client.get("/api/v1/memories", headers=headers),
            client.post(
                "/api/v1/memories",
                json={"kind": "note", "content": "Note"},
                headers=headers,
            ),
            client.patch(
                f"/api/v1/memories/{uuid4()}",
                json={"expected_version": 1, "content": "Note"},
                headers=headers,
            ),
            client.delete(f"/api/v1/memories/{uuid4()}", headers=headers),
            client.get("/api/v1/memory/profile", headers=headers),
        ]
    assert [response.status_code for response in responses] == [401] * len(responses)
    assert all(response.json()["code"] == "unauthorized" for response in responses)
