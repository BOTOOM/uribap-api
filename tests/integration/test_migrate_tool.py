from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

from uribap_api.tools.migrate import main


@pytest.mark.integration
def test_migration_command_is_idempotent_and_leaves_database_at_head(
    integration_engine: Engine,
) -> None:
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    expected_head = ScriptDirectory.from_config(Config(str(config_path))).get_current_head()

    assert main(["--wait-seconds", "2", "--config", str(config_path)]) == 0
    assert main(["--wait-seconds", "2", "--config", str(config_path)]) == 0

    with integration_engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == expected_head
