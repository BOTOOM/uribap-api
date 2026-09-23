from fastapi.testclient import TestClient

from uribap_api.main import app


def test_recipe_version_detail_route_is_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    route = paths["/api/v1/recipes/{recipe_id}/versions/{version_number}"]
    assert "get" in route
    for status in ("401", "403", "404", "422"):
        assert status in route["get"]["responses"], f"missing {status}"


def test_recipe_version_ingredients_route_is_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    route = paths["/api/v1/recipes/{recipe_id}/versions/{version_number}/ingredients"]
    assert "put" in route
    for status in ("401", "403", "404", "422"):
        assert status in route["put"]["responses"], f"missing {status}"
