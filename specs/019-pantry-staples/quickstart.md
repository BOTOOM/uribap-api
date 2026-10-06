# Quickstart: Pantry Staple Ingredients

## Preconditions

- Work on API branch `devin/1791246997-pantry-staples`, based on `origin/main`.
- Confirm `uv run alembic heads` reports the single expected starting head
  `6b1354a22e91` before creating the migration.
- Use the existing Docker PostgreSQL service. Do not stop it after testing.

## Implementation and focused verification

After adding tests first and then implementation, the following gates passed:

```bash
uv run ruff check .
uv run pyright
uv run pytest tests/unit
uv run pytest tests/api
docker compose up -d db
uv run alembic upgrade head
uv run pytest tests/integration
uv run alembic heads
uv run alembic check
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
uv run pip-audit
git diff --check
```

The migration integration test verifies upgrade, the false default for existing rows, downgrade,
and re-upgrade. The targeted changed-file Ruff and format checks also passed:

```bash
uv run ruff format --check migrations/versions/674f2f27ef53_add_pantry_staple_ingredient_flag.py src/uribap_api/infrastructure/persistence/ingredient_models.py src/uribap_api/api/recipe_schemas.py src/uribap_api/application/ingredient_service.py src/uribap_api/api/ingredients.py src/uribap_api/domain/completion/policies.py src/uribap_api/application/completion_service.py src/uribap_api/domain/forecast/policies.py src/uribap_api/application/forecast_service.py src/uribap_api/api/forecast_schemas.py src/uribap_api/domain/planning/entry_detail.py src/uribap_api/application/planning_service.py src/uribap_api/api/plan_schemas.py src/uribap_api/mcp/tools_catalog.py tests/unit/domain/test_completion_policies.py tests/unit/domain/test_forecast_policies.py tests/unit/domain/test_plan_entry_detail.py tests/integration/test_completion_service.py tests/integration/test_forecast_service.py tests/integration/test_plan_entry_detail_routes.py tests/integration/test_ingredient_routes.py tests/integration/test_mcp_ingredients.py tests/integration/test_migrations.py tests/api/test_openapi.py
uv run ruff check tests/integration/test_forecast_service.py tests/integration/test_household_memory_migration.py tests/integration/test_plan_entry_detail_routes.py
uv run ruff format --check tests/integration/test_forecast_service.py tests/integration/test_household_memory_migration.py tests/integration/test_plan_entry_detail_routes.py
```

Results: `ruff check .` reported all checks passed; format checks reported 24 and 3 files already
formatted; Pyright reported 0 errors, warnings, or informations. Unit tests: 226 passed; API tests:
30 passed; integration tests: 178 passed and 2 skipped. The skips require the optional API-container
smoke setup (`RUN_COMPOSE_SMOKE=1`) and disposable local ZITADEL (`RUN_LOCAL_IDENTITY=1`). Pytest
reported the existing Starlette/httpx and AnyIO deprecation warnings. Pyright printed its
non-blocking newer-version notice.

`docker compose up -d db` reused `uribap-api-db-1`, which remained healthy. `alembic heads`
reported `674f2f27ef53 (head)` and `alembic check` reported `No new upgrade operations detected`.
The migration tests downgraded to the parent revision and re-upgraded successfully. OpenAPI
generation was run with `PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi`;
check mode exited successfully with no output. `uv run pip-audit` reported no known
vulnerabilities. `docker stats --no-stream` measured the database at 97.27 MiB / 31.34 GiB
(0.30%); no API container/process was running and the feature plan defines no resource budget.
The plan does not require a Docker API smoke build.

An initial integration attempt was made before upgrading the shared database and failed because the
new `ingredient.pantry_staple` column was not present. After applying `uv run alembic upgrade head`,
the full integration suite passed.

## API behavior checks

- Create, retrieve, update, and list a household ingredient with `pantry_staple` true and false;
  verify a global ingredient update remains 403.
- Complete a recipe with regular ingredients and staples, a zero-stock staple, an all-staple
  recipe, and an actually empty recipe.
- Submit an explicit completion line for a staple and verify status 422, code `validation_error`,
  and the exact contract detail.
- Project positive-stock and empty-stock staple demand, verify non-staple results are unchanged,
  and verify plan-entry detail does not allocate staple stock to subsequent rows.
- Invoke MCP ingredient create, update, and list tools and inspect the returned flag and
  descriptions.

## Contract and submission

The API verification is complete. Commit and push the API branch without waiting for CI; Web
contract synchronization starts only after that push.
