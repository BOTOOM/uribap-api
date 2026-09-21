from fastapi.testclient import TestClient

from uribap_api.main import app


def test_inventory_routes_are_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/inventory" in paths
    assert "/api/v1/inventory/lots" in paths
    assert "/api/v1/inventory/adjustments" in paths
    assert "/api/v1/inventory/lots/{lot_id}/movements" in paths
    assert "Idempotency-Key" in str(paths["/api/v1/inventory/adjustments"])
