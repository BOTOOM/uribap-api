from fastapi.testclient import TestClient

from uribap_api.main import app


def test_shopping_routes_are_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]

    base = paths["/api/v1/shopping-lists"]
    assert set(base.keys()) == {"post"}
    assert "201" in base["post"]["responses"]

    current = paths["/api/v1/shopping-lists/current"]
    assert set(current.keys()) == {"get"}

    by_id = paths["/api/v1/shopping-lists/{list_id}"]
    assert set(by_id.keys()) == {"get"}
    for status in ("401", "403", "404"):
        assert status in by_id["get"]["responses"], f"missing {status}"

    purchase = paths["/api/v1/shopping-lists/{list_id}/items/{item_id}/purchase"]
    assert set(purchase.keys()) == {"post"}
    for status in ("401", "403", "404", "409", "422"):
        assert status in purchase["post"]["responses"], f"missing {status}"

    for suffix in ("skip", "restore"):
        item_route = paths[f"/api/v1/shopping-lists/{{list_id}}/items/{{item_id}}/{suffix}"]
        assert set(item_route.keys()) == {"post"}
        assert "409" in item_route["post"]["responses"]

    for suffix in ("complete", "reopen", "archive"):
        list_route = paths[f"/api/v1/shopping-lists/{{list_id}}/{suffix}"]
        assert set(list_route.keys()) == {"post"}
        assert "409" in list_route["post"]["responses"]
