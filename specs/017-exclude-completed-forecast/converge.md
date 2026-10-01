# Feature 017 Convergence

## Implementation

Implemented forecast exclusion for recorded cooked and skipped completions while retaining approved
plan traceability. Added persisted cooked/skipped completion outcomes, the reversible migration,
skip REST and MCP operations, and tenant-scoped plan-entry detail through the REST API and MCP.
Plan-entry detail includes global ingredient names, returns recipe metadata with an empty ingredient
list for ingredient-free versions, and independently scales each recipe row while omitting rows
that round to zero. The review follow-up extracts detail scaling and stock allocation into the
framework-independent planning domain, filters unavailable, zero, and expired lots against the
later of household-local today and the planned date, and distributes duplicate ingredient/unit
stock in `(position, ingredient_id)` order. Scale overflow now maps to the same validation `422` as
completion. Reopening cooked completions reverses stock; reopening skipped/delivery completions
restores demand without inventory effects. Shopping continues to consume the canonical forecast.
Regenerated `openapi/openapi.json` for the original feature; the review follow-up did not change the
API schema.

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
| API PR #151 quality after dependency remediation | PASS | The earlier `pip-audit` findings (16 vulnerabilities across PyJWT 2.13.0 and urllib3 2.7.0) prompted commit `b7281461476b5ad312f0e2966328922c0e3d3b2a`; PyJWT was upgraded to 2.15.0 and urllib3 to 2.8.0. The subsequent `quality` check passed. |
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
- The branch's PyJWT/urllib3 dependency changes were made to clear `pip-audit` advisories, not to
  add feature runtime dependencies.
- The full suite was not rerun after the focused review fixes, per the updated verification scope.

## Review follow-up

### Receipt payload assessment

`complete_entry`, `correct_line`, and `reopen_completion` all serialize receipts through
`_completion_payload`, which returns the top-level JSON object from
`MealCompletionResponse.model_dump(mode="json")`. The persisted PostgreSQL sample contained 26
`meal_entry_complete` receipts (11 NULL payloads, 7 object payloads missing both outcome keys, and
8 with both keys), plus 41 `meal_entry_skip` receipts with both keys. No correction/reopen rows were
present in the sample, but their shared serializer and storage path are the same; therefore the
receipt shape was unambiguous. NULL payloads remain unchanged. The migration adds
`outcome: "cooked"` and `outcome_note: null` only to object receipts missing top-level `outcome`,
and downgrade removes both keys from object receipts.

### Review verification

| Command/check | Result | Evidence |
| --- | --- | --- |
| `uv run ruff check .` and targeted check of the updated migration test | PASS | All checks passed |
| Ruff format check for changed Python files other than `mcp/tools_plan.py` | PASS | 10 touched files pass; `mcp/tools_plan.py` retains the pre-existing formatting drift confirmed on `origin/main` |
| `uv run pyright` | PASS | 0 errors, 0 warnings, 0 informations |
| `uv run pytest tests/unit -q` | PASS | 182 passed, 2 dependency deprecation warnings |
| `uv run pytest tests/api -q` | PASS | 27 passed, 2 dependency deprecation warnings |
| Focused integration tests for migrations, planning detail, completion, MCP plan tools, and forecast | PASS | 28 passed, 2 dependency deprecation warnings |
| `uv run alembic upgrade head`, migration downgrade/upgrade round trip, and `uv run alembic heads` / `current` | PASS | Review database returned to `d3c72b91a84f`, the single head |
| OpenAPI export `--check` | PASS | Contract unchanged; no generated files edited |
| API PR #151 dependency audit | PASS (prior CI) | The same locked dependencies passed the PR quality job after the PyJWT/urllib3 bump; dependencies were unchanged during this follow-up |
| `docker stats --no-stream uribap-api-db-1` | INFO | 82.12 MiB / 31.34 GiB, 2.79% CPU; no API container was running |

The receipt migration test now downgrades, seeds legacy complete/correct/reopen receipts, upgrades,
replays them, preserves NULL payloads, and verifies downgrade key removal. The source assessment
confirmed the three operations share the same top-level `MealCompletionResponse` serializer.
