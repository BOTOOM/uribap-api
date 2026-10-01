# Feature 017 Convergence

## Implementation

Implemented forecast exclusion for recorded cooked and skipped completions while retaining approved
plan traceability. Added persisted cooked/skipped completion outcomes, the reversible migration,
skip REST and MCP operations, and tenant-scoped plan-entry detail through the REST API and MCP.
Plan-entry detail includes global ingredient names, returns recipe metadata with an empty ingredient
list for ingredient-free versions, and independently scales each recipe row while omitting rows
that round to zero. Shopping continues to consume the canonical forecast. Regenerated
`openapi/openapi.json`.

The migration is `d3c72b91a84f` with parent `f2b8d4e6a917`. The database upgrade/downgrade/upgrade
round trip succeeded, and `uv run alembic heads` reported the single head
`d3c72b91a84f`.

## Verification

| Command | Result | Evidence |
| --- | --- | --- |
| Focused forecast, completion, plan-detail, route, and MCP tests | PASS | 33 passed, 2 dependency deprecation warnings; includes global ingredient names and empty recipe versions |
| Alembic upgrade, downgrade `-1`, upgrade, and heads | PASS | Round trip completed; one head, `d3c72b91a84f` |
| `uv run ruff check src tests` | PASS | All checks passed |
| `uv run ruff check .` | PASS | All checks passed |
| `uv run ruff format --check src tests` | FAIL, accepted | 18 files would be reformatted; the drift is pre-existing on `origin/main`, as confirmed by review. No unrelated bulk formatting was applied. |
| `uv run pyright` | PASS | 0 errors, 0 warnings, 0 informations |
| OpenAPI export and `--check` | PASS | Generated snapshot is current |
| `uv run pytest -q tests/api` | PASS | 27 passed, 2 dependency deprecation warnings |
| `uv run pytest tests/unit` | PASS | 175 passed, 2 dependency deprecation warnings |
| `uv run pytest tests/integration` | FAIL | 128 passed, 2 skipped, 2 failed. The migration-head expectation was updated for the new head and its targeted test then passed. The outbox test failure is caused by persisted pending rows in the reused PostgreSQL database: `process_outbox` selects only the oldest 10, while 11 eligible rows were present. |
| `uv run pytest -q tests/integration/test_migrations.py` | PASS | 1 passed, 2 dependency deprecation warnings |
| Final `uv run pytest -q` | FAIL, accepted | 331 passed, 3 skipped, 1 failed: `tests/integration/test_event_service.py::test_process_outbox_suppresses_without_smtp` left its newly created row pending because older pending rows filled the worker's `limit=10` batch. The local DB is persistent; CI uses a fresh database. No full-suite rerun was requested after this review. |
| `uv run pip-audit` | FAIL | 16 findings in unchanged locked dependencies: PyJWT 2.13.0 (13 CVEs) and urllib3 2.7.0 (3 CVEs). `uv.lock` is unchanged from `origin/main`; dependency updates were outside this feature's scope. |
| `git diff --check` | PASS | No whitespace errors in tracked changes. |

The focused and final test runs emitted the existing Starlette/httpx and AnyIO deprecation warnings.
Pyright also noted a newer version is available; the configured version passed.

## Environment and scope

The local PostgreSQL container was reused; no ZITADEL, Mailpit, or full Compose stack was started.
`docker stats --no-stream` showed the existing `uribap-api-db-1` at 63.49 MiB / 31.34 GiB
(0.20% memory, 0.00% CPU); no API container was started. Docker build/smoke tests were not required
by this feature plan.

## Accepted verification exceptions

- Repository-wide Ruff format check remains non-clean due baseline formatting drift; no unrelated
  bulk reformatting was applied.
- The local full-suite result is not green because the reused test database contains older pending
  outbox entries. The integration test assumes its new row is within the first 10 globally ordered
  rows; CI uses a fresh database, so this was accepted as non-blocking.
- `pip-audit` reports pre-existing dependency vulnerabilities listed above.
- The full suite was not rerun after the focused review fixes, per the updated verification scope.
