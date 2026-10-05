# Feature 018 Convergence

## Implementation

Implemented household-scoped diner profiles and durable household/diner memories with soft
archives, optimistic versions, idempotent creates, and privacy-minimized mutation events. Added
the reversible migration `6b1354a22e91` after `d3c72b91a84f`, REST CRUD/profile routes, seven MCP
tools, the active memory profile in `uribap_get_context`, and the generated OpenAPI contract.
Regression coverage spans domain schemas, PostgreSQL services and routes, MCP tools/transport,
migration structure, tenant isolation, idempotency, and event privacy.

## Ordered verification

| Command | Result | Evidence |
| --- | --- | --- |
| Focused unit/integration/API/MCP/migration tests | PASS | `uv run pytest tests/unit/domain/test_household_memory.py tests/integration/test_household_memory_service.py tests/integration/test_household_memory_routes.py tests/integration/test_mcp_memory_tools.py tests/integration/test_mcp_transport.py tests/integration/test_household_memory_migration.py tests/integration/test_migrations.py tests/api/test_household_memory_routes.py -q` — 32 passed, 2 dependency deprecation warnings |
| Alembic upgrade/downgrade/upgrade and heads | PASS | Round trip completed; `uv run alembic heads` reported `6b1354a22e91 (head)` |
| `uv run ruff check src tests` | PASS | All checks passed |
| Touched-file `uv run ruff format --check` | PASS | 19 Python files already formatted |
| `uv run pyright` | PASS | 0 errors, 0 warnings, 0 informations |
| OpenAPI export, `--check`, and contract tests | PASS | Exporter generated the artifact; `--check` exited 0; focused API contract test passed |
| Final `uv run pytest -q` | PASS | 362 passed, 3 skipped, 2 dependency deprecation warnings |
| `git diff --check` | PASS | No whitespace errors |

## Additional project gates

- `uv run pytest tests/unit -q` — 188 passed; `uv run pytest tests/api -q` — 29 passed.
- Final `uv run pytest tests/integration -q` — 145 passed, 2 skipped. An earlier run had one
  failure in the existing `test_process_outbox_suppresses_without_smtp`; its isolated rerun and
  subsequent full integration rerun passed after the reused database state changed. No feature
  code change was needed for that test.
- `uv run pip-audit` — no known vulnerabilities found.
- The existing PostgreSQL container was reused. A local sample reported 0.01% CPU and
  66.08 MiB / 31.34 GiB memory (0.21%). No API container was running to sample. The plan adds no
  runtime service and defines no separate numeric resource budget.
- Docker image build/smoke checks were not run because the feature plan does not require a Docker
  build or runtime change.
- `devin models list --format json` was unavailable; the lead-approved exception and AGENTS.md
  model-matrix selection are recorded in `plan.md` and `analyze.md`.

## Deviations and scope

The authoritative design was followed without Web changes, new dependencies, or runtime
infrastructure. The model-list CLI unavailability is the accepted, documented exception. The
reused-database outbox test passed on the final integration rerun and full suite.

## Devin Review Follow-up

Added optional caller-supplied idempotency keys to `uribap_add_diner` and `uribap_remember`,
including length validation and same-key replay coverage. `uribap_update_diner` now requires
`unlink_member=true` to explicitly remove a member link and rejects combining that flag with
`member_user_id`. Invalid/inactive/foreign and already-linked account associations use
`invalid_member_link` while preserving their previous status, title, and detail.

Memory creation and reassignment now validate the diner with `FOR UPDATE`, using the same diner-row
lock as the existing archive operation. The PostgreSQL regression verifies blocking behavior and
that each operation emits a diner `SELECT ... FOR UPDATE`. `get_memory_profile` fetches all active
household and diner memories once, groups them in Python, and preserves the existing ordering.
OpenAPI remained unchanged; the export `--check` passed.

API C's initial merge from API B conflicted only in `tests/integration/test_migrations.py`. The
resolution retained C's dynamic current-head/single-head assertion and combined B's legacy
completion-receipt migration/replay test. It removed the stale fixed-revision assertion that could
not hold after C's `6b1354a22e91` migration; Ruff/Pyright also caught and the merge follow-up added
the missing `ScriptDirectory` import.

Regression tests were added before the implementation. The initial focused run showed 6 expected
failures and 8 passes, including the old error code, profile query count, MCP tool description, and
missing caller-key behavior. Final focused tests passed (16 passed); after strengthening the lock
test to assert the generated SQL, its targeted rerun passed (1 passed).

| Check | Result | Evidence |
| --- | --- | --- |
| `uv run ruff check src tests` and `uv run ruff check .` | PASS | Both reported “All checks passed.” |
| Repository `uv run ruff format --check` | BASELINE DRIFT | The repo-wide run reported 18 unformatted files, including the then-new service-test lines. All six changed Python files were subsequently checked with `uv run ruff format --check` and passed; no unrelated files were reformatted. |
| `uv run pyright` | PASS | 0 errors, 0 warnings, 0 informations. The final modified concurrency test also passed a file-scoped Pyright run. |
| `uv run pytest tests/unit -q` | PASS | 195 passed, 2 dependency deprecation warnings. |
| `uv run pytest tests/api -q` | PASS | 29 passed, 2 dependency deprecation warnings. |
| Focused route/service/MCP/migration tests | PASS | 16 passed, 2 dependency deprecation warnings. |
| Final lock regression | PASS | 1 passed after adding the SQL `FOR UPDATE` assertion. |
| Alembic upgrade/downgrade/upgrade and heads | PASS | Round trip completed; `6b1354a22e91 (head)` is the single head. |
| OpenAPI export `--check` | PASS | No contract changes. |
| `uv run pip-audit` | PASS | No known vulnerabilities found. |
| Full `uv run pytest` | PASS | 374 passed, 3 skipped, 2 dependency deprecation warnings. The only later edit was a test-only SQL lock assertion, verified with the targeted lock test (1 passed). |
| `docker stats --no-stream` | INFO | PostgreSQL `uribap-api-db-1`: 2.61% CPU, 83.07 MiB / 31.34 GiB memory; no API container was running. |

The full repository formatter check continues to report unrelated baseline drift; focused formatting
checks on all changed Python files passed. No generated schema was changed or hand-edited.
