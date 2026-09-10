from fastapi.testclient import TestClient

from uribap_api.main import app


def test_identity_and_household_routes_are_in_openapi() -> None:
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/api/v1/me" in paths
    assert "/api/v1/households" in paths
    assert "/api/v1/invitations/accept" in paths
    assert "/api/v1/health/identity" in paths
