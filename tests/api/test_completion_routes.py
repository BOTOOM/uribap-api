from fastapi.testclient import TestClient

from uribap_api.main import app


def test_completion_routes_are_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]

    complete = paths["/api/v1/plans/{plan_id}/entries/{entry_id}/complete"]
    assert set(complete.keys()) == {"post"}
    assert "201" in complete["post"]["responses"]
    for status in ("401", "403", "404", "409", "422"):
        assert status in complete["post"]["responses"], f"missing {status}"

    base = paths["/api/v1/meal-completions"]
    assert set(base.keys()) == {"get"}
    for status in ("401", "403", "422"):
        assert status in base["get"]["responses"], f"missing {status}"

    detail = paths["/api/v1/meal-completions/{completion_id}"]
    assert set(detail.keys()) == {"get"}
    for status in ("401", "403", "404"):
        assert status in detail["get"]["responses"], f"missing {status}"

    correct = paths["/api/v1/meal-completions/{completion_id}/lines/{line_id}/correct"]
    assert set(correct.keys()) == {"post"}
    for status in ("401", "403", "404", "409", "422"):
        assert status in correct["post"]["responses"], f"missing {status}"

    reopen = paths["/api/v1/meal-completions/{completion_id}/reopen"]
    assert set(reopen.keys()) == {"post"}
    for status in ("401", "403", "404", "409", "422"):
        assert status in reopen["post"]["responses"], f"missing {status}"
