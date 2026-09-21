import pytest

from uribap_api.domain.recipes.policies import (
    RecipeVersionState,
    can_edit_version,
    can_publish_version,
    validate_lead_minutes,
    validate_servings,
)


def test_published_versions_are_immutable_by_policy() -> None:
    assert can_edit_version(RecipeVersionState.DRAFT)
    assert not can_edit_version(RecipeVersionState.PUBLISHED)
    assert can_publish_version(RecipeVersionState.DRAFT)
    assert not can_publish_version(RecipeVersionState.ARCHIVED)


def test_recipe_validation_rejects_invalid_values() -> None:
    assert validate_servings(2) == 2
    assert validate_lead_minutes(30) == 30
    with pytest.raises(ValueError):
        validate_servings(0)
    with pytest.raises(ValueError):
        validate_lead_minutes(-1)
