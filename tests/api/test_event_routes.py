from fastapi.testclient import TestClient

from uribap_api.main import app


def test_activity_route_is_exposed_in_openapi() -> None:
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]

    activity = paths["/api/v1/households/{household_id}/activity"]
    assert set(activity.keys()) == {"get"}
    for status in ("401", "403", "404"):
        assert status in activity["get"]["responses"], f"missing {status}"
    params = {param["name"] for param in activity["get"].get("parameters", [])}
    assert {"household_id", "page", "page_size"} <= params
