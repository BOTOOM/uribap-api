import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
def test_security_headers_on_api_route(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "camera=()" in response.headers["permissions-policy"]
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers["content-security-policy"]


@pytest.mark.api
def test_security_headers_on_error_response(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.api
def test_docs_paths_still_reachable(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_default_settings_keep_email_delivery_disabled() -> None:
    from uribap_api.config import Settings

    settings = Settings(environment="test")
    assert settings.email_delivery_enabled is False
