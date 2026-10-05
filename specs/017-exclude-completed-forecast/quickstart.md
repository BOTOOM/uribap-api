# Quickstart: Validate Completed Meal Forecast and Detail APIs

## Prerequisites

- PostgreSQL integration test database configured as required by the repository.
- Dependencies synchronized with `uv sync --locked`.
- The configured local PostgreSQL service is running and reachable.

## Focused validation

Run the existing forecast tests and all changed/new completion, detail, route, and MCP tests:

```bash
uv run pytest \
  tests/unit/domain/test_plan_entry_detail.py \
  tests/integration/test_migrations.py \
  tests/integration/test_forecast_service.py \
  tests/integration/test_completion_service.py \
  tests/integration/test_plan_entry_detail.py \
  tests/integration/test_plan_completion_routes.py \
  tests/integration/test_plan_entry_detail_routes.py \
  tests/integration/test_mcp_transport.py \
  tests/integration/test_mcp_plan_tools.py \
  tests/api/test_completion_routes.py \
  tests/api/test_planning_routes.py \
  -q
```

Expected behavior includes:

- Cooked and skipped recorded completions both suppress only their own entry's demand; reopening
  restores demand while approved plan ids remain traceable.
- Skipping persists outcome/note and an event without completion lines, inventory movements, or lot
  balance changes; duplicate or non-approved requests return `409`, and cross-household entries
  return `404`.
- Idempotent skip replay returns the original response.
- Plan detail scales servings with `planned_lines`, excludes unavailable lots, reports optional
  lines and shortfalls, embeds only the current recorded completion, and rejects foreign entries.
- Plan detail omits zero-rounded rows, allocates eligible stock deterministically across duplicate
  ingredient/unit rows, and applies the household-local/planned-date expiry cutoff. Scale overflow
  maps to the same validation `422` as completion.
- Reopening cooked completions reverses inventory consumption; reopening skipped or delivery
  completions restores demand without inventory reversals.
- MCP tools list and invoke the skip and detail operations.

## Migration and contract validation

```bash
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
uv run alembic heads
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
```

The migration must return to the single head and the generated OpenAPI check must pass.

## Resource sample

During review verification, `docker stats --no-stream uribap-api-db-1` reported **82.12 MiB /
31.34 GiB** and **2.79% CPU**. The API container was not running, so its process memory was not
sampled. The feature plan defines no quantitative resource budget.
