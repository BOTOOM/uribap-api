from fastapi.testclient import TestClient

from uribap_api.main import app


def test_forecast_route_is_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    route = paths["/api/v1/forecast/demand"]
    assert "get" in route
    assert set(route.keys()) == {"get"}
    for status in ("401", "403", "422"):
        assert status in route["get"]["responses"], f"missing {status}"
    params = {param["name"] for param in route["get"]["parameters"]}
    assert {"from_date", "to_date"} <= params
