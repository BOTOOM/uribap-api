from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import OperationalError

from uribap_api.tools import migrate


class FakeConnection:
    def __init__(self) -> None:
        self.locked = False
        self.unlocked = False
        self.closed = False

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.closed = True

    def execute(self, statement: Any, _parameters: Any = None) -> None:
        sql = str(statement)
        if "pg_advisory_lock" in sql:
            self.locked = True
        elif "pg_advisory_unlock" in sql:
            self.unlocked = True


class FakeEngine:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.connect_calls = 0
        self.connections: list[FakeConnection] = []
        self.disposed = False

    def connect(self) -> FakeConnection:
        self.connect_calls += 1
        if self.connect_calls <= self.failures:
            raise OperationalError("SELECT 1", {}, RuntimeError("connection refused"))
        connection = FakeConnection()
        self.connections.append(connection)
        return connection

    def dispose(self) -> None:
        self.disposed = True


def prepare_engine(
    monkeypatch: pytest.MonkeyPatch,
    engine: FakeEngine,
    *,
    upgrade: Any = None,
) -> None:
    monkeypatch.setattr(migrate, "get_settings", lambda: object())
    monkeypatch.setattr(migrate, "create_database_engine", lambda _settings: engine)
    if upgrade is not None:
        monkeypatch.setattr(migrate.command, "upgrade", upgrade)


def test_main_retries_database_connection_then_upgrades(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine = FakeEngine(failures=1)
    sleeps: list[float] = []
    clock = [0.0]
    upgrades: list[tuple[str, bool]] = []

    def upgrade(_config: Any, revision: str) -> None:
        upgrades.append((revision, engine.connections[-1].locked))

    def advance_clock(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    prepare_engine(monkeypatch, engine, upgrade=upgrade)
    monkeypatch.setattr(migrate, "monotonic", lambda: clock[0])
    monkeypatch.setattr(migrate, "sleep", advance_clock)

    assert migrate.main(["--wait-seconds", "10"]) == 0

    assert engine.connect_calls == 3
    assert sleeps == [2]
    assert upgrades == [("head", True)]
    assert engine.connections[-1].unlocked
    assert engine.disposed
    assert "migrations: at head " in capsys.readouterr().out


def test_main_exits_after_database_wait_budget(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine = FakeEngine(failures=10)
    sleeps: list[float] = []
    clock = [0.0]

    def advance_clock(seconds: float) -> None:
        sleeps.append(seconds)
        clock[0] += seconds

    prepare_engine(monkeypatch, engine)
    monkeypatch.setattr(migrate, "monotonic", lambda: clock[0])
    monkeypatch.setattr(migrate, "sleep", advance_clock)

    assert migrate.main(["--wait-seconds", "4"]) == 1

    assert engine.connect_calls == 3
    assert sleeps == [2, 2]
    assert engine.disposed
    assert "database unavailable after waiting for 4 seconds" in capsys.readouterr().err


def test_main_unlocks_advisory_lock_when_upgrade_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakeEngine()

    def upgrade(_config: Any, _revision: str) -> None:
        assert engine.connections[-1].locked
        raise RuntimeError("migration failed")

    prepare_engine(monkeypatch, engine, upgrade=upgrade)

    assert migrate.main(["--wait-seconds", "0"]) == 1

    assert engine.connections[-1].unlocked
    assert engine.connections[-1].closed
    assert engine.disposed
