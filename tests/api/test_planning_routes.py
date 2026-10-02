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
    detail_path = "/api/v1/plans/{plan_id}/entries/{entry_id}/detail"
    assert detail_path in paths
    detail = paths[detail_path]["get"]
    for status in ("200", "401", "403", "404", "422"):
        assert status in detail["responses"], f"detail missing {status}"
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

    detail_schema = client.get("/openapi.json").json()["components"]["schemas"][
        "MealPlanEntryDetailResponse"
    ]
    assert {
        "entry_id",
        "plan_id",
        "plan_state",
        "planned_date",
        "meal_type",
        "servings",
        "notes",
        "recipe_id",
        "recipe_name",
        "recipe_description",
        "recipe_version_id",
        "version_number",
        "base_servings",
        "prep_minutes",
        "ingredients",
        "completion",
    }.issubset(detail_schema["properties"])
    components = client.get("/openapi.json").json()["components"]["schemas"]
    ingredient_ref = detail_schema["properties"]["ingredients"]["items"]["$ref"]
    ingredient_schema = components[ingredient_ref.rsplit("/", 1)[-1]]
    assert {
        "ingredient_id",
        "ingredient_name",
        "required_amount",
        "unit",
        "optional",
        "on_hand_amount",
        "shortfall_amount",
        "position",
    }.issubset(ingredient_schema["properties"])
