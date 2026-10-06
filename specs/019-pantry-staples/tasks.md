# Tasks: Pantry Staple Ingredients

**Input**: `spec.md`, `plan.md`, `data-model.md`, and contracts in this feature directory  
**Tests**: Domain and PostgreSQL integration/MCP behavior regressions must be written before
implementation and run in the final verification pass.

## Phase 1: Setup and design gate

- [x] T001 Verify branch base and single Alembic head `6b1354a22e91`; complete requirements checklist,
  domain/data model, API contracts, implementation plan, and analysis before product changes.

## Phase 2: Pantry-staple domain regressions

> Write these focused regressions before changing domain or application behavior; run them with the
> final verification pass.

- [x] T002 Add forecast policy cases for a staple with demand greater than positive on-hand, a
  zero-stock staple, and unchanged non-staple behavior in
  `tests/unit/domain/test_forecast_policies.py`.
- [x] T003 Add completion policy cases for staple exclusion, all-staple zero lines, truly empty
  recipe error, exact validation for explicit staple actuals, and regular-line behavior in
  `tests/unit/domain/test_completion_policies.py`.
- [x] T004 Add plan-entry detail cases for stocked/empty staples and verify staple rows do not reduce
  shared stock in `tests/unit/domain/test_plan_entry_detail.py`.

## Phase 3: REST, MCP, migration, and PostgreSQL regressions

> Author behavior regressions before implementing persistence, adapters, or service behavior.

- [x] T005 Add ingredient REST create/get/update tests for the flag and global update 403 in
  `tests/integration/test_ingredient_routes.py`.
- [x] T006 Extend `tests/integration/test_migrations.py` with upgrade/default/downgrade/upgrade
  coverage for the new revision.
- [x] T007 Add forecast and completion PostgreSQL regressions for stocked/empty staples, no staple
  deductions or completion lines, all-staple recipes, and explicit-line 422 in the existing
  forecast/completion integration suites.
- [x] T008 Add MCP ingredient create/update/list flag and tool-description coverage in
  `tests/integration/test_mcp_ingredients.py`.
- [x] T009 Extend API/OpenAPI assertions for ingredient, forecast, and plan-entry response fields in
  focused `tests/api/` contract tests.

## Phase 4: Persistence and domain implementation

- [x] T010 Add the reversible server-default-false migration after revision `6b1354a22e91`, add the
  model field, and update ingredient create/update/response schemas and service mappings.
- [x] T011 Add pantry status to REST response construction and MCP row/create/update/list contracts;
  preserve global ingredient read-only behavior.
- [x] T012 Exclude staples from completion consumption lines, distinguish all-staple recipes from
  empty recipe versions, and reject explicit staple actual lines with the exact 422 detail.
- [x] T013 Carry pantry status through forecast demand and apply staple-only shortfall behavior;
  include the field in forecast response schema/service.
- [x] T014 Carry pantry status through plan-entry detail domain/service/schema; calculate staple
  shortfall from zero on-hand and preserve shared stock for later rows.

## Phase 5: Contract, verification, and convergence

- [x] T015 Regenerate `openapi/openapi.json` with the official exporter; pass its check and relevant
  OpenAPI tests.
- [x] T016 Run targeted Ruff, format, Pyright, unit/integration/API/MCP, migration, Alembic head,
  and OpenAPI checks; record exact commands and results in `quickstart.md`.
- [ ] T017 Record final diff, commit and push SHA, migration head, test evidence, deviations, and
  remaining verification limitations in `converge.md`.

## Dependencies and execution order

- T001 is the specification gate and precedes all tests and product changes.
- T002–T008 are authored before T010–T014. T009 validates the completed schemas and generated
  contract; tests may be grouped by domain and integration scope.
- T010–T014 precede T015 because OpenAPI is generated from the final schemas.
- T016 and T017 complete before the API branch is pushed and the Web contract is synchronized.
