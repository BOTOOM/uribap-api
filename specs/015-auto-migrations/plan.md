# Plan — 015 Automatic migrations on API startup

## Models

- Primary: `gpt-5-6-sol-high` (implementation). Reviewer: `gpt-5-6-terra-high`
  (deployment and failure-safety review). Subagent: `swe-2-high` (bounded test fixes).
- Model IDs taken from the AGENTS.md matrix (2026-09-10); `devin models list` unavailable in this environment.

## Design

No schema change or dependency is required. Add
`src/uribap_api/tools/migrate.py` using `get_settings()` and
`create_database_engine()`. Probe the database with `SELECT 1`, catching
`OperationalError` and retrying within the configured wait budget. On a dedicated
connection, acquire a fixed PostgreSQL session advisory lock, invoke
`alembic.command.upgrade(Config(config_path), "head")`, then unlock in `finally`;
always dispose the engine. Default the Alembic config to the repository root relative
to the module, with a `--config` override.

The Docker image and Compose API command run the migration module before Uvicorn unless
`MIGRATE_ON_START=false`; Uvicorn must be `exec`'d and the image healthcheck gets a
60-second start period. The lock serializes overlapping containers and migration errors
fail the new container before it can receive traffic.

## Files and verification

- Module: `src/uribap_api/tools/migrate.py`
- Runtime: `Dockerfile`, `compose.yml`, `.env.example`
- Operations guidance: `docs/operations/coolify.md`,
  `docs/operations/foundation.md`
- Tests: `tests/unit/test_migrate_tool.py`,
  `tests/integration/test_migrate_tool.py`
- Run Ruff, pyright, new tests, `uv run pytest tests/unit tests/integration -q`,
  and `uv run alembic check`. Build and run the image against a fresh disposable
  PostgreSQL database, verify first and repeat startup plus failed-database behavior,
  then remove only the test resources and leave the development database running.

## Rolling-release constraint

The old container remains active while the new one starts. Schema changes must remain
backward-compatible and additive within a release; keep the existing rollback guidance.
