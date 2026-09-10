from uuid import uuid4

from fastapi.testclient import TestClient

from uribap_api.main import app


def test_invitation_routes_require_authentication() -> None:
    household_id = uuid4()
    invitation_id = uuid4()
    with TestClient(app) as client:
        responses = [
            client.get(f"/api/v1/households/{household_id}/invitations"),
            client.post(
                f"/api/v1/households/{household_id}/invitations",
                json={"email": "synthetic@example.test", "role": "member"},
            ),
            client.delete(f"/api/v1/households/{household_id}/invitations/{invitation_id}"),
            client.post("/api/v1/invitations/accept", json={"token": "synthetic-token-value"}),
        ]
    assert [response.status_code for response in responses] == [401, 401, 401, 401]
    assert all(response.json()["code"] == "unauthorized" for response in responses)
