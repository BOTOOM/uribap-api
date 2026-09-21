import pytest
from sqlalchemy import inspect

from uribap_api.config import get_settings
from uribap_api.infrastructure.database import create_database_engine


@pytest.mark.integration
def test_inventory_schema_is_present_after_migration() -> None:
    engine = create_database_engine(get_settings())
    try:
        tables = set(inspect(engine).get_table_names())
        assert {"inventory_lot", "inventory_movement"}.issubset(tables)
    finally:
        engine.dispose()
