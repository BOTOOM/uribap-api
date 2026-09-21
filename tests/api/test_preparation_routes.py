from fastapi.testclient import TestClient

from uribap_api.main import app


def test_preparation_routes_are_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]

    base = paths["/api/v1/preparation-tasks"]
    assert set(base.keys()) == {"get", "post"}
    assert "201" in base["post"]["responses"]
    for status in ("401", "403", "409", "422"):
        assert status in base["post"]["responses"], f"missing {status}"
    for status in ("401", "403"):
        assert status in base["get"]["responses"], f"missing {status}"

    for suffix in ("complete", "cancel"):
        route = paths[f"/api/v1/preparation-tasks/{{task_id}}/{suffix}"]
        assert set(route.keys()) == {"post"}
        for status in ("401", "403", "404", "409", "422"):
            assert status in route["post"]["responses"], f"missing {status} in {suffix}"

    rules = paths["/api/v1/recipes/{recipe_id}/versions/{version_id}/preparation-rules"]
    assert set(rules.keys()) == {"post"}
    assert "201" in rules["post"]["responses"]

    rule_by_id = paths[
        "/api/v1/recipes/{recipe_id}/versions/{version_id}/preparation-rules/{rule_id}"
    ]
    assert set(rule_by_id.keys()) == {"delete"}
    assert "204" in rule_by_id["delete"]["responses"]
