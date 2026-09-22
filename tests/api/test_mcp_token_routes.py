from uuid import uuid4

from fastapi.testclient import TestClient

from uribap_api.main import app


def test_mcp_token_routes_are_exposed_in_openapi() -> None:
    with TestClient(app) as client:
        paths = client.get("/openapi.json").json()["paths"]
    base = "/api/v1/households/{household_id}/mcp-tokens"
    assert base in paths
    assert f"{base}/{{token_id}}" in paths
    assert "post" in paths[base]
    assert "get" in paths[base]
    assert "delete" in paths[f"{base}/{{token_id}}"]


def test_mcp_token_routes_require_authentication() -> None:
    household_id = uuid4()
    with TestClient(app) as client:
        responses = [
            client.get(f"/api/v1/households/{household_id}/mcp-tokens"),
            client.post(
                f"/api/v1/households/{household_id}/mcp-tokens", json={"name": "Devin"}
            ),
            client.delete(f"/api/v1/households/{household_id}/mcp-tokens/{uuid4()}"),
        ]
    assert [response.status_code for response in responses] == [401, 401, 401]
    assert all(response.json()["code"] == "unauthorized" for response in responses)
