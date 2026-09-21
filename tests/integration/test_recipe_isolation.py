import pytest
from sqlalchemy import inspect

from uribap_api.config import get_settings
from uribap_api.infrastructure.database import create_database_engine


@pytest.mark.integration
def test_recipe_schema_is_present_after_migration() -> None:
    engine = create_database_engine(get_settings())
    try:
        tables = set(inspect(engine).get_table_names())
        assert {
            "ingredient",
            "recipe",
            "recipe_version",
            "recipe_version_ingredient",
            "recipe_instruction",
            "recipe_meal_type",
            "recipe_tag",
            "recipe_tag_link",
            "recipe_favorite",
            "recipe_preparation_rule",
        }.issubset(tables)
    finally:
        engine.dispose()
