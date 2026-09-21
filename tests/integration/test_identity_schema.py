import pytest
from sqlalchemy import inspect, text

from uribap_api.config import get_settings
from uribap_api.infrastructure.database import create_database_engine


@pytest.mark.integration
def test_identity_schema_has_expected_tables() -> None:
    engine = create_database_engine(get_settings())
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        expected = {
            "app_user",
            "user_identity",
            "household",
            "household_member",
            "household_invitation",
            "audit_event",
            "email_outbox_entry",
        }
        assert expected.issubset(tables)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
    finally:
        engine.dispose()
