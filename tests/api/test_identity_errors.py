from fastapi.testclient import TestClient

from uribap_api.infrastructure.identity.jwt_validator import TokenValidator
from uribap_api.main import app


def test_protected_route_requires_bearer_token() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/me")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "unauthorized"
    assert response.json()["detail"] == "A bearer token is required."


def test_identity_health_is_unavailable_when_not_configured(monkeypatch) -> None:
    async def not_ready(self) -> bool:
        del self
        return False

    monkeypatch.setattr(TokenValidator, "ready", not_ready)
    with TestClient(app) as client:
        response = client.get("/api/v1/health/identity")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
