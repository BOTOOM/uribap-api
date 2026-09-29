# 015 — Automatic migrations on API startup

## Problem

The first Coolify deployment required a manual `alembic upgrade head`. Repeating that
operator step for each release is error-prone. With rolling updates, the old API
container continues serving while the new one starts, so migration startup must be
serialized, fail safely, and preserve compatibility with the old container.

## Scope

- Add `python -m uribap_api.tools.migrate`: wait for PostgreSQL, take a session-level
  advisory lock, upgrade to Alembic head, and always release the lock and dispose the
  engine. Support `--wait-seconds` (default 60) and `--config`; do not log credentials.
- Run migrations before Uvicorn by default in the Docker image and development Compose.
  A failed migration must prevent Uvicorn startup; `MIGRATE_ON_START=false` opts out.
- Document startup behavior, lock/fail semantics, rolling-release compatibility
  requirements, and the explicit migration opt-out.

## Out of scope

- Alembic downgrades or automated rollback.
- Coolify UI configuration or deployment changes.

## Acceptance

- Unit tests cover retry/success, timeout failure, advisory-lock ordering, and unlock
  after migration failure; an integration test proves repeated runs are idempotent.
- A built image applies migrations to a fresh database before serving readiness, starts
  cleanly a second time without new migrations, and exits non-zero for a bad database URL.
- Ruff, pyright, unit/integration tests, and `alembic check` pass.
