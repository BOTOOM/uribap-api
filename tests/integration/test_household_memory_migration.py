from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration


def test_household_memory_migration_is_single_head_after_feature_017(
    integration_engine: Engine,
) -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = scripts.get_heads()

    assert len(heads) == 1
    revision = scripts.get_revision(heads[0])
    assert revision is not None
    assert revision.down_revision == "d3c72b91a84f"
    assert "household_memory" in Path(revision.path).name

    with integration_engine.connect() as connection:
        database_revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert database_revision == heads[0]

    inspector = inspect(integration_engine)
    assert inspector.has_table("household_diner")
    assert inspector.has_table("household_memory")
    diner_columns = {column["name"]: column for column in inspector.get_columns("household_diner")}
    assert getattr(diner_columns["display_name"]["type"], "length", None) == 80
    assert diner_columns["member_user_id"]["nullable"] is True
    assert diner_columns["archived_at"]["nullable"] is True
    assert diner_columns["version"]["nullable"] is False
    assert diner_columns["version"]["default"] is not None
    diner_foreign_keys = inspector.get_foreign_keys("household_diner")
    assert any(
        key["constrained_columns"] == ["household_id"]
        and key["referred_table"] == "household"
        and key.get("options", {}).get("ondelete") == "CASCADE"
        for key in diner_foreign_keys
    )
    assert any(
        key["constrained_columns"] == ["member_user_id"]
        and key["referred_table"] == "app_user"
        and key.get("options", {}).get("ondelete") == "SET NULL"
        for key in diner_foreign_keys
    )
    diner_constraints = inspector.get_unique_constraints("household_diner")
    assert any(item["name"] == "uq_household_diner_member" for item in diner_constraints)
    diner_indexes = inspector.get_indexes("household_diner")
    assert any(
        item["name"] == "uq_household_diner_active_name" and item["unique"]
        for item in diner_indexes
    )
    active_name_index = next(
        item for item in diner_indexes if item["name"] == "uq_household_diner_active_name"
    )
    assert "archived_at IS NULL" in active_name_index.get("dialect_options", {}).get(
        "postgresql_where", ""
    )

    memory_columns = {
        column["name"]: column for column in inspector.get_columns("household_memory")
    }
    assert getattr(memory_columns["kind"]["type"], "length", None) == 16
    assert memory_columns["content"]["nullable"] is False
    assert memory_columns["diner_id"]["nullable"] is True
    assert memory_columns["created_by_user_id"]["nullable"] is True
    assert memory_columns["version"]["nullable"] is False
    assert memory_columns["version"]["default"] is not None
    memory_foreign_keys = inspector.get_foreign_keys("household_memory")
    assert any(
        key["constrained_columns"] == ["household_id"]
        and key["referred_table"] == "household"
        and key.get("options", {}).get("ondelete") == "CASCADE"
        for key in memory_foreign_keys
    )
    assert any(
        key["constrained_columns"] == ["diner_id"]
        and key["referred_table"] == "household_diner"
        and key.get("options", {}).get("ondelete") == "CASCADE"
        for key in memory_foreign_keys
    )
    assert any(
        key["constrained_columns"] == ["created_by_user_id"]
        and key["referred_table"] == "app_user"
        and key.get("options", {}).get("ondelete") == "SET NULL"
        for key in memory_foreign_keys
    )
    memory_checks = inspector.get_check_constraints("household_memory")
    assert any(item["name"] == "ck_household_memory_kind" for item in memory_checks)
    memory_indexes = inspector.get_indexes("household_memory")
    assert any(
        item["column_names"] == ["household_id", "diner_id", "archived_at"]
        for item in memory_indexes
    )
