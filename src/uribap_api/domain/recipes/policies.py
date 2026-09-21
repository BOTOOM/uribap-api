from enum import StrEnum


class RecipeVersionState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class RecipeMealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class PreparationRuleType(StrEnum):
    DEFROST = "defrost"
    SOAK = "soak"
    MARINATE = "marinate"
    PREPARE_AHEAD = "prepare_ahead"


def can_edit_version(state: RecipeVersionState) -> bool:
    return state == RecipeVersionState.DRAFT


def can_publish_version(state: RecipeVersionState) -> bool:
    return state == RecipeVersionState.DRAFT


def validate_servings(servings: int) -> int:
    if servings <= 0:
        raise ValueError("base servings must be positive")
    return servings


def validate_lead_minutes(minutes: int) -> int:
    if minutes < 0:
        raise ValueError("lead minutes cannot be negative")
    return minutes
