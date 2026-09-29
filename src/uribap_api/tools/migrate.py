"""Apply Alembic migrations before starting the API.

Usage: python -m uribap_api.tools.migrate [--wait-seconds N] [--config PATH]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from time import monotonic, sleep

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from uribap_api.config import get_settings
from uribap_api.infrastructure.database import create_database_engine

MIGRATION_ADVISORY_LOCK_ID = 0x7572696261705F6D


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _wait_for_database(engine: Engine, wait_seconds: int) -> bool:
    deadline = monotonic() + wait_seconds
    while True:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("migrations: database connection ready", flush=True)
            return True
        except OperationalError:
            remaining = deadline - monotonic()
            if remaining <= 0:
                print(
                    f"migrations: database unavailable after waiting for {wait_seconds} "
                    "seconds; aborting startup",
                    file=sys.stderr,
                    flush=True,
                )
                return False
            sleep(min(2, remaining))


def _upgrade(engine: Engine, config_path: Path) -> str | None:
    config = Config(str(config_path))
    with engine.connect() as connection:
        locked = False
        try:
            connection.execute(
                text("SELECT pg_advisory_lock(:lock_id)"),
                {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
            )
            locked = True
            print("migrations: upgrading to head", flush=True)
            command.upgrade(config, "head")
        finally:
            if locked:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": MIGRATION_ADVISORY_LOCK_ID},
                )
    return ScriptDirectory.from_config(config).get_current_head()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply database migrations to Alembic head.")
    parser.add_argument("--wait-seconds", type=int, default=60)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.wait_seconds < 0:
        print("migrations: --wait-seconds must be nonnegative", file=sys.stderr)
        return 1

    engine: Engine | None = None
    try:
        engine = create_database_engine(get_settings())
        if not _wait_for_database(engine, args.wait_seconds):
            return 1
        config_path = args.config or _project_root() / "alembic.ini"
        head = _upgrade(engine, config_path)
        print(f"migrations: at head {head or 'unknown'}", flush=True)
        return 0
    except Exception as exc:
        print(
            f"migrations: startup failed ({type(exc).__name__}); API startup aborted",
            file=sys.stderr,
            flush=True,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
