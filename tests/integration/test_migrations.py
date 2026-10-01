import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text


@pytest.mark.integration
def test_current_migration_head_is_applied(integration_engine: Engine) -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = scripts.get_heads()
    assert len(heads) == 1

    with integration_engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == heads[0]
