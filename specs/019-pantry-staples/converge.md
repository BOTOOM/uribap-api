# Convergence: Pantry Staple Ingredients

## Status

Implementation and local verification are complete; commit and push are pending.

## Expected delivery

- Branch: `devin/1791246997-pantry-staples`.
- Base: API `origin/main` at `44bfb80dfa1c8e161e557f61a607bc75a625abaa`.
- Starting Alembic head: `6b1354a22e91`.
- Migration: one reversible `ingredient.pantry_staple` Boolean with server default false.
- Canonical contract: `openapi/openapi.json`, regenerated with the repository exporter.

## Verification record

To be completed after implementation:

| Check | Command | Result |
|---|---|---|
| Ruff | `uv run ruff check .` | Pass: all checks passed; final edits also passed targeted Ruff |
| Ruff format | Changed-file Ruff format checks in `quickstart.md` | Pass: all checked files formatted |
| Type check | `uv run pyright` | Pass: 0 errors, 0 warnings, 0 informations |
| Unit tests | `uv run pytest tests/unit` | Pass: 226 passed |
| API tests | `uv run pytest tests/api` | Pass: 30 passed |
| Integration tests | `uv run pytest tests/integration` | Pass: 178 passed, 2 optional tests skipped |
| Migration | `uv run alembic upgrade head`; migration integration tests in full integration suite | Pass: upgrade, default, downgrade, and re-upgrade |
| Alembic | `uv run alembic heads && uv run alembic check` | Pass: `674f2f27ef53 (head)`; no new upgrade operations |
| OpenAPI | `PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check` | Pass: exit 0 |
| Security | `uv run pip-audit` | Pass: no known vulnerabilities |
| Resource sample | `docker stats --no-stream` | DB: 97.27 MiB / 31.34 GiB; no API container/process or feature budget |
| Diff | `git diff --check` | Pending final documentation edit |

## Workflow notes

- The domain and PostgreSQL/MCP behavior regressions were authored before implementation. The
  OpenAPI schema-field assertion was added after the schemas and before final API verification.
- The first focused integration attempt ran against the database before the new migration had been
  applied; it failed on the missing column. After `uv run alembic upgrade head`, the complete
  integration suite passed.

## Final result

Implementation and verification complete. Commit, push, SHA, diff stat, and final diff check are
pending.
