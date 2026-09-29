from fastapi.testclient import TestClient

from uribap_api.main import app


def test_recipe_lifecycle_routes_are_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    routes = {
        "/api/v1/recipes/{recipe_id}": "patch",
        "/api/v1/recipes/{recipe_id}/revisions": "post",
        "/api/v1/recipes/{recipe_id}/archive": "post",
        "/api/v1/recipes/{recipe_id}/unarchive": "post",
    }

    for path, method in routes.items():
        operation = paths[path][method]
        for status in ("401", "403", "404", "409", "422"):
            assert status in operation["responses"], f"{method.upper()} {path} missing {status}"

    assert paths["/api/v1/recipes/{recipe_id}/revisions"]["post"]["responses"]["201"]
