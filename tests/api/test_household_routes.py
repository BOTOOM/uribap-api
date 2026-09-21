from uuid import uuid4

from fastapi.testclient import TestClient

from uribap_api.main import app


def test_household_routes_require_authentication() -> None:
    household_id = uuid4()
    with TestClient(app) as client:
        responses = [
            client.post("/api/v1/households", json={"name": "Casa"}),
            client.get(f"/api/v1/households/{household_id}"),
            client.patch(f"/api/v1/households/{household_id}", json={"name": "Nueva casa"}),
            client.get(f"/api/v1/households/{household_id}/members"),
            client.delete(f"/api/v1/households/{household_id}/members/{uuid4()}"),
        ]
    assert [response.status_code for response in responses] == [401, 401, 401, 401, 401]
    assert all(response.json()["code"] == "unauthorized" for response in responses)
