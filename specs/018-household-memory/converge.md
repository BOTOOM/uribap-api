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
