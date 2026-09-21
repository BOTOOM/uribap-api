from enum import StrEnum


class IngredientDimension(StrEnum):
    COUNT = "count"
    MASS = "mass"
    VOLUME = "volume"


UNIT_DIMENSIONS: dict[str, IngredientDimension] = {
    "unit": IngredientDimension.COUNT,
    "g": IngredientDimension.MASS,
    "kg": IngredientDimension.MASS,
    "ml": IngredientDimension.VOLUME,
    "l": IngredientDimension.VOLUME,
}


def normalize_ingredient_name(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    if not 1 <= len(normalized) <= 160:
        raise ValueError("ingredient name must contain between 1 and 160 characters")
    if any(ord(char) < 32 for char in normalized):
        raise ValueError("ingredient name must not contain control characters")
    return normalized


def validate_unit_for_dimension(dimension: IngredientDimension, unit: str) -> str:
    if UNIT_DIMENSIONS.get(unit) != dimension:
        raise ValueError("unit does not match ingredient dimension")
    return unit


def normalize_quantity(dimension: IngredientDimension, amount: str, unit: str) -> tuple[str, str]:
    validate_unit_for_dimension(dimension, unit)
    if not amount or amount.startswith("-"):
        raise ValueError("quantity must be positive")
    try:
        numeric = float(amount)
    except ValueError as exc:
        raise ValueError("quantity must be numeric") from exc
    if numeric <= 0:
        raise ValueError("quantity must be positive")
    return amount, unit
