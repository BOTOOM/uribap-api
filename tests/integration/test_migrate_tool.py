from pathlib import Path
from threading import Event, Thread

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text

from uribap_api.tools.migrate import MIGRATION_ADVISORY_LOCK_ID, main


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


@pytest.mark.integration
def test_migration_command_waits_for_advisory_lock(integration_engine: Engine) -> None:
    finished = Event()
    results: list[int] = []

    def run_migration() -> None:
        try:
            results.append(main(["--wait-seconds", "2"]))
        finally:
            finished.set()

    with integration_engine.connect() as lock_connection:
        lock_connection.execute(
            text("SELECT pg_advisory_lock(:lock_id)"),
            {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
        )
        worker = Thread(target=run_migration, daemon=True)
        worker.start()
        still_waiting = not finished.wait(timeout=1)
        lock_connection.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
        )
        lock_connection.commit()
        worker.join(timeout=10)

    assert still_waiting
    assert not worker.is_alive()
    assert results == [0]
