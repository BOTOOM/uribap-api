import pytest

from uribap_api.domain.ingredients.policies import (
    IngredientDimension,
    normalize_ingredient_name,
    normalize_quantity,
    validate_unit_for_dimension,
)


def test_units_match_dimensions_without_cross_dimension_guessing() -> None:
    assert validate_unit_for_dimension(IngredientDimension.MASS, "kg") == "kg"
    assert normalize_quantity(IngredientDimension.VOLUME, "500", "ml") == ("500", "ml")
    with pytest.raises(ValueError):
        validate_unit_for_dimension(IngredientDimension.MASS, "ml")
    with pytest.raises(ValueError):
        normalize_quantity(IngredientDimension.COUNT, "0", "unit")


def test_ingredient_name_normalization_is_deterministic() -> None:
    assert normalize_ingredient_name("  Red   Pepper ") == "red pepper"
    with pytest.raises(ValueError):
        normalize_ingredient_name("\n")
