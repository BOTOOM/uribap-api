# Quickstart: Preparation

```bash
uv sync --locked
uv run ruff check .
uv run pyright
uv run pytest tests/unit
uv run pytest tests/api
docker compose up -d db
uv run alembic upgrade head
uv run pytest tests/integration
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
uv run pip-audit
```

Seed a recipe version with a `defrost` rule, approve a plan containing it, then
`GET /preparation-tasks` — one pending task appears with `due_at = meal start − lead`.
Complete it, verify `409` on a stale `expected_version`, re-approve after removing the
entry and see the task cancelled. Create a manual task and replay with the same
`Idempotency-Key`.

## Evidence

Validated 2026-10-05 against clean PostgreSQL `uribap_ci` (all migrations applied,
`alembic check` reports no drift):

- `ruff check` + `ruff format --check`: clean.
- `pyright`: 0 errors.
- `tests/unit/domain/test_preparation_policies.py`: 9 passed (transitions, version,
  timezone fallback, lead bounds, `due_at` per meal type, fingerprint determinism,
  manual-task validation).
- `tests/integration/test_preparation_schema.py`: 5 passed (columns, CHECKs, composite
  FK tenancy, derived-fingerprint partial uniqueness, operation idempotency).
- `tests/integration/test_preparation_service.py`: 8 passed (approve-time derivation,
  idempotent re-approval with stale-task cancellation, manual validation, tenancy,
  transitions with `expected_version`, Europe/Madrid `due_at`, no-rules no-tasks).
- `tests/api/test_preparation_routes.py`: passed (OpenAPI route/method/error-shape
  assertions).
- Full suite: `136 passed, 3 skipped`.
- `openapi/openapi.json` regenerated with `preparation-tasks` and `preparation-rules`
  paths; `pip-audit`: no known vulnerabilities.
