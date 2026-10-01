import pytest

from uribap_api.main import app

pytestmark = pytest.mark.api


def test_household_memory_openapi_contains_exact_routes_and_models() -> None:
    document = app.openapi()
    paths = document["paths"]
    expected_methods = {
        "/api/v1/diners": {"get", "post"},
        "/api/v1/diners/{diner_id}": {"patch", "delete"},
        "/api/v1/memories": {"get", "post"},
        "/api/v1/memories/{memory_id}": {"patch", "delete"},
        "/api/v1/memory/profile": {"get"},
    }
    for path, methods in expected_methods.items():
        assert path in paths
        assert methods.issubset(paths[path])

    schemas = document["components"]["schemas"]
    assert set(schemas["DinerResponse"]["properties"]) == {
        "id",
        "display_name",
        "member_user_id",
        "archived_at",
        "version",
        "created_at",
        "updated_at",
    }
    assert set(schemas["MemoryResponse"]["properties"]) == {
        "id",
        "diner_id",
        "kind",
        "content",
        "archived_at",
        "version",
        "created_by_user_id",
        "created_at",
        "updated_at",
    }
    assert "expected_version" in schemas["DinerUpdate"]["required"]
    assert "expected_version" in schemas["MemoryUpdate"]["required"]
    assert set(schemas["MemoryCreate"]["required"]) == {"kind", "content"}
    assert set(schemas["DinerPage"]["properties"]) == {"items"}
    assert set(schemas["MemoryPage"]["properties"]) == {"items"}
    assert set(schemas["HouseholdMemoryProfile"]["properties"]) == {
        "household",
        "diners",
    }


def test_household_memory_openapi_documents_errors_idempotency_and_filters() -> None:
    paths = app.openapi()["paths"]
    for path, method in (
        ("/api/v1/diners", "get"),
        ("/api/v1/diners", "post"),
        ("/api/v1/diners/{diner_id}", "patch"),
        ("/api/v1/diners/{diner_id}", "delete"),
        ("/api/v1/memories", "get"),
        ("/api/v1/memories", "post"),
        ("/api/v1/memories/{memory_id}", "patch"),
        ("/api/v1/memories/{memory_id}", "delete"),
        ("/api/v1/memory/profile", "get"),
    ):
        response_codes = set(paths[path][method]["responses"])
        assert {"401", "403", "404", "422"}.issubset(response_codes)

    assert "409" in paths["/api/v1/diners"]["post"]["responses"]
    assert "409" in paths["/api/v1/diners/{diner_id}"]["patch"]["responses"]
    assert "409" in paths["/api/v1/memories"]["post"]["responses"]
    assert "409" in paths["/api/v1/memories/{memory_id}"]["patch"]["responses"]
    assert "204" in paths["/api/v1/diners/{diner_id}"]["delete"]["responses"]
    assert "204" in paths["/api/v1/memories/{memory_id}"]["delete"]["responses"]

    diner_parameters = paths["/api/v1/diners"]["post"]["parameters"]
    assert any(parameter["name"] == "Idempotency-Key" for parameter in diner_parameters)
    memory_parameters = paths["/api/v1/memories"]["post"]["parameters"]
    assert any(parameter["name"] == "Idempotency-Key" for parameter in memory_parameters)

    memory_get_parameters = {
        parameter["name"]: parameter for parameter in paths["/api/v1/memories"]["get"]["parameters"]
    }
    assert {"diner_id", "scope", "include_archived", "limit"}.issubset(memory_get_parameters)
    assert memory_get_parameters["scope"]["schema"]["default"] == "all"
    assert memory_get_parameters["include_archived"]["schema"]["default"] is False
    assert memory_get_parameters["limit"]["schema"]["default"] == 200
    diner_get_parameters = {
        parameter["name"]: parameter for parameter in paths["/api/v1/diners"]["get"]["parameters"]
    }
    assert diner_get_parameters["include_archived"]["schema"]["default"] is False
