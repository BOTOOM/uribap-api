import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
def test_unknown_route_uses_problem_details(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    payload = response.json()
    assert payload["code"] == "http_404"
    assert payload["requestId"].startswith("req_")
    assert "traceback" not in response.text.lower()


@pytest.mark.api
def test_request_id_is_returned_and_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/health/live", headers={"x-request-id": "req_test_123"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req_test_123"
