# Implementation Plan: Completed Meal Outcomes and Plan Entry Detail

**Branch**: `devin/1790817968-exclude-completed-forecast` | **Date**: 2026-10-01 |
**Spec**: [spec.md](spec.md)

## Summary

Deliver three connected API capabilities: exclude every recorded completion from forecast demand;
record a cooked or skipped outcome without changing the existing recorded/reopened lifecycle; and
read a single plan entry with scaled recipe lines, available stock, shortfalls, and its recorded
completion. Shopping generation continues to use the canonical forecast.

## Models

- Primary: `gpt-5-6-sol-high` (implementation). Reviewer: `gpt-5-6-terra-high`
  (domain and transaction review). Subagent: `swe-2-high` (bounded test fixes). Escalate to the
  lead if the authoritative interfaces conflict with the current schema or require a design choice.
- These identifiers are from the AGENTS.md model matrix. `devin models list --format json` was
  attempted, but the `devin` CLI is unavailable in this environment.

## Technical Context

**Language/Version**: Python 3.13+

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Pydantic

**Storage**: PostgreSQL; add outcome columns to the existing `meal_completion` table.

**Testing**: pytest integration/API/MCP tests against PostgreSQL, Ruff, Pyright, Alembic, generated
OpenAPI validation

**Target Platform**: Linux container on Coolify

**Project Type**: FastAPI web service and MCP server

**Performance Goals**: Use a correlated `NOT EXISTS` for recorded completions, reuse existing
indexes, and avoid per-entry queries in the forecast path. Plan detail may perform bounded reads
for the single requested entry and its ingredients, lots, and completion.

**Constraints**: Forecast/detail remain deterministic and read-only; all quantity arithmetic uses
`Decimal`; skip is transactional, tenant-scoped, idempotent, and creates no inventory effects.

**Scale/Scope**: One additive migration, two API endpoints, two MCP tools, forecast filtering, and
focused integration/API/MCP coverage. No new dependency, table, service, or frontend change.

## Design

### A. Forecast excludes recorded completions

In `src/uribap_api/application/forecast_service.py`, exclude entries with a correlated
`NOT EXISTS` for `MealCompletion` matching the requesting household, entry id, and
`MealCompletionState.RECORDED`. Keep approved plan selection and `considered_plan_ids` unchanged;
reopened completions naturally remain eligible. Shopping generation inherits the behavior from
`demand_forecast`.

### B. Cooked and skipped completion outcomes

- Add `MealCompletionOutcome` (`cooked`, `skipped`) in
  `src/uribap_api/domain/completion/policies.py`.
- Add non-native enum `outcome` and nullable `outcome_note` columns to
  `MealCompletion` in `src/uribap_api/infrastructure/persistence/completion_models.py`.
  The outcome is non-null, defaults to cooked in Python and the database, and is guarded by
  `ck_meal_completion_outcome`.
- Add one additive Alembic revision in `migrations/versions/` with `down_revision =
  "f2b8d4e6a917"`; use a `cooked` server default for existing rows and drop both columns on
  downgrade.
- Add `MealCompletionSkip` and extend `MealCompletionResponse` in
  `src/uribap_api/api/completion_schemas.py`.
- Add `skip_entry` to `src/uribap_api/application/completion_service.py`, following
  `complete_entry` plan/entry/tenant validation and its receipt/fingerprint flow with operation
  `meal_entry_skip`. Persist a `RECORDED`/`SKIPPED` completion and reason with zero lines and zero
  inventory movements. Record the specified `MEAL_COMPLETED` payload; cooked events also gain
  `outcome: "cooked"`. Reopen keeps its existing transition and reversal logic, which is a no-op
  when no lines exist.
- Add `POST /{plan_id}/entries/{entry_id}/skip` to the existing plan-completion router in
  `src/uribap_api/api/completion.py`, returning `201` and the updated response.

### C. Read-only plan-entry detail

- Add `MealPlanEntryDetailResponse` and `MealPlanEntryIngredientLine` to
  `src/uribap_api/api/plan_schemas.py` with the exact fields in the contract.
- Implement `get_entry_detail(session, membership, plan_id, entry_id)` in
  `src/uribap_api/application/planning_service.py`, scoping plan and entry to the membership's
  household and returning `404` on a foreign or absent resource.
- Reuse `planned_lines` from `domain/completion/policies.py` for scaled ingredient amounts;
  do not create a second scaling formula. Sum available same-household, same-ingredient, same-unit
  inventory lots, then derive nonnegative shortfalls. Order lines by recipe position then id.
  Include the recipe's description and current recorded completion only.
- Add `GET /{plan_id}/entries/{entry_id}/detail` to `src/uribap_api/api/plans.py`.
- Register `uribap_skip_meal` (WRITE, title `Mark meal as not cooked`) in
  `src/uribap_api/mcp/tools_plan.py` with the exact description: "Record that a planned meal was
  not cooked at home (delivery, ate out, skipped). Removes it from forecast and shopping demand
  without touching inventory. Reopen the completion to undo." Update the cooked-completion tool
  description to state that cooked meals also leave forecast/shopping demand.
- Register `uribap_get_plan_entry` (READ_ONLY, title `Plan entry detail`) in the same MCP module and
  return the detail response payload.

### Migration and contract

OpenAPI changes are additive, but still require regeneration. Export with
`PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi`; verify with the same command
plus `--check`. No web client or MCP protocol version change is included.

## Constitution Check

*Rechecked after the design expansion.*

- **Domain correctness**: Pass. Both recorded outcomes resolve a planned meal; skip does not
  represent physical consumption and therefore creates no inventory movement.
- **Deterministic services**: Pass. Forecast and detail queries remain read-only, and scaling reuses
  the existing domain policy.
- **Test-first critical path**: Required. Add forecast, skip, detail, route, and MCP regressions
  before product code changes.
- **Tenant isolation**: Pass when completion exclusion and detail reads scope household and entry.
- **Contract-first evolution**: Pass. Update schemas, route tests, and generated OpenAPI.
- **Resource-aware simplicity**: Pass. One additive migration, existing tables/indexes, no new
  infrastructure.
- **Auditable operations**: Pass. Skip records a domain event; no fake inventory consumption is
  recorded.
- **UV tooling**: Required for all Python checks.

## Project Structure

```text
src/uribap_api/
├── api/
│   ├── completion.py
│   ├── completion_schemas.py
│   ├── plan_schemas.py
│   └── plans.py
├── application/
│   ├── completion_service.py
│   ├── forecast_service.py
│   └── planning_service.py
├── domain/completion/policies.py
├── infrastructure/persistence/completion_models.py
└── mcp/tools_plan.py
migrations/versions/ (new completion outcome revision)
openapi/openapi.json
tests/
├── api/test_completion_routes.py
├── api/test_planning_routes.py
├── integration/test_forecast_service.py
├── integration/test_completion_service.py
├── integration/test_plan_entry_detail.py
├── integration/test_plan_completion_routes.py
├── integration/test_plan_entry_detail_routes.py
├── integration/test_mcp_transport.py
└── integration/test_mcp_plan_tools.py
```

**Structure Decision**: Extend the existing completion/planning domain and application services.
Use integration tests with the existing PostgreSQL fixture for transactional, inventory, and
tenant guarantees; keep OpenAPI definitions in the canonical generated artifact.

## Required Verification

Run in this order:

1. `uv run pytest tests/integration/test_forecast_service.py tests/integration/test_completion_service.py tests/integration/test_plan_entry_detail.py tests/integration/test_plan_completion_routes.py tests/integration/test_plan_entry_detail_routes.py tests/integration/test_mcp_transport.py tests/integration/test_mcp_plan_tools.py tests/api/test_completion_routes.py tests/api/test_planning_routes.py -q`
2. `uv run alembic upgrade head`, `uv run alembic downgrade -1`, then `uv run alembic upgrade head`;
   `uv run alembic heads` must report one head.
3. `uv run ruff check src tests` and `uv run ruff format --check src tests`.
4. `uv run pyright`.
5. Regenerate OpenAPI with the repository tool and pass its `--check` plus contract/snapshot tests.
6. `uv run pytest -q`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | No constitutional violations identified. | Not applicable. |
