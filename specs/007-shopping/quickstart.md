# Quickstart: Shopping

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

Seed an approved plan with a shortfall, `POST /shopping-lists` for the window, purchase one item (verify the lot + `purchase` movement + item status change atomically), skip another, then complete the list. Replays and duplicate-window generation MUST return the stored result or `409`.

## Evidence

Recorded during convergence (run against a clean PostgreSQL database `uribap_ci` at
revision `c7d4e2f8a915`; `alembic check` reports no pending operations — the canonical
schema includes the hardened inventory shape, unlike the pre-existing dev database):

- `uv run ruff check .` — pass
- `uv run ruff format --check .` — pass
- `uv run pyright` — 0 errors, 0 warnings
- `uv run pytest tests/unit` — pass (12 shopping policy tests included)
- `uv run pytest tests/api` — pass (`test_shopping_routes.py` covers all 9 routes and
  Problem Details responses)
- `uv run pytest tests/integration` — pass against `uribap_ci`
  (`test_shopping_schema.py`: 5 schema/idempotency/tenant tests;
  `test_shopping_service.py`: 8 tests covering generation from the deterministic
  projection, atomic purchase → lot + `purchase` movement + item status, idempotent
  replay, key-hash conflict, skip/restore, complete/reopen/archive, version conflicts,
  tenant isolation, and read-only plan behavior)
- Full suite: `113 passed, 2 skipped`
- `uv run alembic upgrade head` — applied to `c7d4e2f8a915`
- `uv run alembic check` — no new upgrade operations detected
- `PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi` — regenerated;
  `/api/v1/shopping-lists*` routes present
- `uv run pip-audit` — no known vulnerabilities
- `docker build -t uribap-api:007` — pass; container answers `200` on
  `/api/v1/health/live`

The historical dev database retains the pre-hardening `f4` inventory shape documented
in phase 004; the clean `uribap_ci` database is the canonical verification target, as
in CI.
