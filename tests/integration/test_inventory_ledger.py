import pytest
from sqlalchemy import inspect, text

from uribap_api.config import get_settings
from uribap_api.infrastructure.database import create_database_engine


@pytest.mark.integration
def test_inventory_schema_enforces_ledger_invariants() -> None:
    engine = create_database_engine(get_settings())
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert {"inventory_lot", "inventory_movement"}.issubset(tables)
        lot_constraints = {
            item["name"] for item in inspector.get_unique_constraints("inventory_lot")
        }
        movement_constraints = {
            item["name"] for item in inspector.get_unique_constraints("inventory_movement")
        }
        movement_foreign_keys = {
            item["name"] for item in inspector.get_foreign_keys("inventory_movement")
        }
        assert "uq_inventory_lot_household" in lot_constraints
        assert "uq_inventory_movement_idempotency" in movement_constraints
        assert "fk_inventory_movement_lot_household" in movement_foreign_keys
        with engine.connect() as connection:
            trigger = connection.execute(
                text("SELECT 1 FROM pg_trigger WHERE tgname = 'inventory_movement_append_only'")
            ).scalar_one_or_none()
        assert trigger == 1
    finally:
        engine.dispose()
