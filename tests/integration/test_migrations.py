import pytest
from sqlalchemy import Engine, text


@pytest.mark.integration
def test_foundation_migration_is_applied(integration_engine: Engine) -> None:
    with integration_engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == "a8e4b2c1d603"
