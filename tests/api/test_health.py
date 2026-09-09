import pytest
from fastapi.testclient import TestClient

import uribap_api.api.health as health_module


@pytest.mark.api
def test_liveness_does_not_require_database(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "Uribap API"


@pytest.mark.api
def test_readiness_reports_database_dependency(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_database_check(_engine: object) -> bool:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(health_module, "database_is_ready", fail_database_check)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["dependencies"]["database"]["status"] == "unavailable"
    assert response.json()["requestId"] is None or response.json()["requestId"].startswith("req_")
