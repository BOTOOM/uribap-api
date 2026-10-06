import pytest

from uribap_api.main import app


@pytest.mark.api
def test_openapi_contains_foundation_routes_and_problem_details() -> None:
    document = app.openapi()

    assert "/api/v1/health/live" in document["paths"]
    assert "/api/v1/health/ready" in document["paths"]
    assert document["info"]["title"] == "Uribap API"


@pytest.mark.api
def test_openapi_is_deterministic() -> None:
    assert app.openapi() == app.openapi()


@pytest.mark.api
def test_openapi_exposes_pantry_staple_contract_fields() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert schemas["IngredientCreate"]["properties"]["pantry_staple"]["default"] is False
    assert "pantry_staple" in schemas["IngredientUpdate"]["properties"]
    assert "pantry_staple" in schemas["IngredientResponse"]["required"]
    assert "pantry_staple" in schemas["DemandForecastLine"]["required"]
    assert "pantry_staple" in schemas["MealPlanEntryDetailIngredientResponse"]["required"]
