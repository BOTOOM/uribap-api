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

    skip = paths["/api/v1/plans/{plan_id}/entries/{entry_id}/skip"]
    assert set(skip.keys()) == {"post"}
    assert "201" in skip["post"]["responses"]
    assert "Idempotency-Key" in str(skip["post"]["parameters"])
    for status in ("401", "403", "404", "409", "422"):
        assert status in skip["post"]["responses"], f"skip missing {status}"

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

    completion_schema = client.get("/openapi.json").json()["components"]["schemas"][
        "MealCompletionResponse"
    ]
    assert {"outcome", "outcome_note"}.issubset(completion_schema["properties"])
    outcome_ref = completion_schema["properties"]["outcome"]["$ref"]
    outcome_schema = client.get("/openapi.json").json()["components"]["schemas"][
        outcome_ref.rsplit("/", 1)[-1]
    ]
    assert set(outcome_schema["enum"]) == {"cooked", "skipped"}
