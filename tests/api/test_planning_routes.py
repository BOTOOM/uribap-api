from fastapi.testclient import TestClient

from uribap_api.main import app


def test_planning_routes_are_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/plans" in paths
    assert "/api/v1/plans/current" in paths
    assert "/api/v1/plans/{plan_id}" in paths
    assert "/api/v1/plans/{plan_id}/entries" in paths
    assert "/api/v1/plans/{plan_id}/entries/{entry_id}" in paths
    for action in ("propose", "approve", "reopen", "archive"):
        assert f"/api/v1/plans/{{plan_id}}/{action}" in paths
    assert "/api/v1/plans/{plan_id}/events" in paths
    entries = paths["/api/v1/plans/{plan_id}/entries"]
    assert "Idempotency-Key" in str(entries)
    for verb in ("post", "patch", "delete"):
        route = paths["/api/v1/plans/{plan_id}/entries/{entry_id}"].get(verb) or entries.get(verb)
        if route:
            for status in ("401", "403", "404", "409", "422"):
                assert status in route["responses"], f"{verb} missing {status}"
