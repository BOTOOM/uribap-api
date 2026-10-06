# Implementation Plan: Pantry Staple Ingredients

**Branch**: `devin/1791246997-pantry-staples` | **Date**: 2026-10-06  
**Spec**: [spec.md](spec.md)

## Summary

Persist a household ingredient's pantry-staple status and carry it through REST, MCP, recipe
completion, forecast, and plan-entry detail. Pantry staples remain recipe and forecast demand but
are not consumed when cooking. Forecast and detail shortfalls are server-computed so staples only
appear unavailable when their on-hand balance is zero.

## Models

- Primary architecture: `gpt-5-6-luna-max`; implementation: `gpt-5-6-sol-high`;
  reviewer: `gpt-5-6-terra-high`; long-context analysis: `glm-5-3-max`;
  bounded fixes: `swe-2-high`.
- These model identifiers come from the API `AGENTS.md` matrix. The environment's `devin` model
  listing is not available; the identifiers are not represented as CLI-verified.

## Technical Context

**Language/Version**: Python 3.13+  
**Primary Dependencies**: FastAPI, SQLAlchemy 2, Pydantic  
**Storage**: PostgreSQL; one additive Boolean column on `ingredient`  
**Testing**: pytest domain and PostgreSQL integration/MCP tests, Ruff, Pyright, Alembic, canonical
OpenAPI exporter  
**Target Platform**: Linux container on Coolify  
**Project Type**: FastAPI service and MCP server

**Constraints**:

- Add one reversible Alembic migration with `down_revision = "6b1354a22e91"`; verify the base
  contains exactly one head before generating the revision.
- Keep domain calculations framework-independent. Use `Decimal` for all quantities and preserve
  existing completion transaction, tenancy, idempotency, and movement rules.
- Ingredient flag defaults false for existing and new data. Global ingredients remain read-only.
- Forecast required/optional/total demand and shopping-list generation retain their current source
  and behavior; only pantry shortfall changes.
- No new dependency. Do not hand-edit the generated OpenAPI document.

## Design

### A. Ingredient persistence and catalog interfaces

- Add `pantry_staple: Mapped[bool]` to
  `src/uribap_api/infrastructure/persistence/ingredient_models.py`.
- Add the server-default-false Boolean column in a new migration after `6b1354a22e91`.
- Add the default-false create field, optional update field, and always-present response field in
  `src/uribap_api/api/recipe_schemas.py`; include it in REST response construction and ingredient
  service updates.
- Extend the MCP ingredient row, create/update arguments and `IngredientCreate`/`IngredientUpdate`
  construction in `src/uribap_api/mcp/tools_catalog.py`. List/create/update descriptions must
  explain in one sentence that staples are not consumed when cooking and are needed in shopping
  only after stock is depleted.
- Keep household scoping and the existing global-update 403 unchanged.

### B. Completion excludes pantry staples

- Extend `RecipeIngredientInput` with a default-false staple flag and exclude staples before
  constructing consumable lines in `planned_lines`.
- Preserve the existing empty-recipe validation only when the recipe version truly has no
  ingredients. When the recipe contains ingredients but all are staples, return an empty planned
  line list.
- In `complete_entry`, fetch pantry status for recipe-version ingredients. Reject payload lines
  naming a staple with the exact specified validation detail before persistence or inventory
  allocation.
- Keep skip/delivery, correction, reopen, and completion movement reversal unchanged.

### C. Forecast keeps demand but changes staple shortfall

- Carry `pantry_staple` from the recipe ingredient join through
  `RecipeIngredientDemand`, aggregated demand, and projected lines in
  `src/uribap_api/domain/forecast/policies.py`.
- In `apply_on_hand`, calculate staple shortfall as total demand when available on-hand is exactly
  zero, otherwise zero; keep the existing `max(total - available, 0)` rule for non-staples.
- Expose the field in `DemandForecastLine` and the application response mapping. Do not change
  shopping-list creation.

### D. Plan-entry detail carries pantry status without stock allocation

- Carry `pantry_staple` through `RecipeIngredientRow`, `EntryDetailIngredient`, the planning query,
  and `MealPlanEntryDetailIngredientResponse`.
- For a staple, return the current on-hand balance, calculate shortfall as required amount only when
  that balance is zero, and leave shared `remaining_stock` unchanged.
- Preserve existing deterministic ordering, expiration filtering, duplicate-row allocation, and
  non-staple semantics.

### E. Tests first and contract generation

- Add domain regressions for forecast, completion, and entry-detail rules before implementation.
- Add PostgreSQL integration coverage for ingredient REST behavior, migration up/down, forecast and
  completion flows, and MCP create/update/list.
- Regenerate `openapi/openapi.json` with `PYTHONPATH=src uv run python -m
  uribap_api.tools.export_openapi`; verify using the exporter's check mode and contract tests.

## Verification

Run after the final API edit:

```bash
uv run ruff check <changed-python-files>
uv run ruff format --check <changed-python-files>
uv run pyright
uv run pytest <touched-unit-test-files> <touched-integration-test-files> <touched-api-test-files>
uv run alembic heads
uv run alembic upgrade head
uv run alembic check
uv run pytest tests/integration/test_migrations.py
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
git diff --check
```

Use the existing Docker PostgreSQL container for integration/migration checks and leave it running.
Commit and push the API branch after verification; do not wait for CI.

## Constitution Check

- **Domain ownership**: Completion, forecast, and detail rules remain in framework-independent
  domain policies; the API computes all quantities.
- **Decimal safety**: Existing `Decimal` amounts are retained throughout new calculations.
- **Tenant boundaries**: Only household ingredients are editable; global update remains HTTP 403.
- **Data integrity**: The migration is additive/reversible, with a false server default.
- **Test-first**: Domain and integration regressions precede product implementation.
- **Contract integrity**: OpenAPI is regenerated with the official exporter after schema changes.

## Analyze Resolution

The settled feature design explicitly distinguishes a zero-ingredient recipe from a recipe that
contains only staples. Completion tests cover both states and verify zero persisted lines for the
all-staple recipe. Staple lines remain in forecast demand; only the server-side shortfall rule
changes. Entry-detail staples never consume shared stock. No unresolved design choice remains.
