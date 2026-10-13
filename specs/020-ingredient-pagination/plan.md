# Implementation Plan: Ingredient Catalog Pagination

**Branch**: `devin/1791306650-ingredient-pagination` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/020-ingredient-pagination/spec.md`

## Summary

Add stable cursor pagination to the REST and MCP ingredient catalogs. Reuse the existing ingredient
filters and page-size bounds, order by `(normalized_name, id)`, fetch one extra row to determine
whether another page exists, and expose the continuation value through the existing typed
`PageInfo`. Invalid cursors use the established `DomainError` and Problem Details path. No
persistent data or migration is required.

## Technical Context

**Language/Version**: Python 3.14

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Pydantic; Python standard library for base64,
JSON, and UUID cursor encoding/validation

**Storage**: Existing PostgreSQL `ingredient` rows; no schema changes

**Testing**: pytest with the existing PostgreSQL integration fixtures, Ruff, Pyright, generated
OpenAPI checks, and MCP integration tests

**Target Platform**: Linux API service and connected MCP clients

**Project Type**: Python backend API and MCP service

**Performance Goals**: Return no more than the requested page size; use a keyset boundary and
fetch at most one additional row to detect continuation, with the existing maximum page size of
100.

**Constraints**: Preserve household/global visibility and query/dimension filters; clients repeat
filters when continuing. Cursor contents are not persisted. Use the existing error and contract
patterns and UV for all Python execution. Pages are not a snapshot across concurrent catalog edits.

**Scale/Scope**: Household ingredient catalogs may exceed 100 entries; acceptance coverage
includes a 140-ingredient catalog and small two-item pages.

**Model guidance**:

- Primary architecture model: `gpt-5-6-luna-max`; implementation model: `gpt-5-6-sol-high`.
- Reviewer model: `gpt-5-6-terra-high`.
- Subagent model: `swe-2-high` for bounded test/type work; `glm-5-3-max` for long-context artifact
  analysis.
- Escalation: `kimi-k3-max` only for explicit cross-repo escalation.
- These identifiers are cited from `AGENTS.md`; the owner’s current model-policy decision means
  CLI verification is not required. The pantry base branch still contains the prior wording in its
  constitution, so this plan follows the explicit current decision without changing the required
  feature branch ancestry.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Domain correctness**: Pass. Pagination is a read-only projection and does not alter inventory
  or quantities.
- **Deterministic services**: Pass. The application service applies filters before a stable
  lexicographic keyset boundary.
- **Test-first critical paths**: Pass. Add service/API, filter, cursor-error, and MCP regressions
  before implementation.
- **Tenant isolation**: Pass. Existing active-household and optional-global predicates remain in
  every page query; the cursor is not an authorization boundary.
- **Contract-first evolution**: Pass. Type the ingredient `page_info`, document the cursor, and
  regenerate the canonical OpenAPI artifact.
- **Resource-aware simplicity**: Pass. Reuse current query/service infrastructure; add no table,
  index, dependency, or external service.
- **Reproducible operations**: Pass. Use the repository exporter and UV commands; no migration is
  required.
- **Model policy**: Follow the owner’s explicit current decision from Part 2 and cite the model
  identifiers in `AGENTS.md` without CLI verification. The inherited pantry constitution predates
  that decision; no model identifier lookup is required for this plan.

## Project Structure

### Documentation (this feature)

```text
specs/020-ingredient-pagination/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/ingredient-listing.md
├── checklists/
├── analysis.md
├── converge.md
└── tasks.md
```

### Source Code (repository root)

```text
src/uribap_api/
├── api/
│   ├── ingredients.py
│   ├── recipe_schemas.py
│   └── schemas.py
├── application/ingredient_service.py
└── mcp/tools_catalog.py
openapi/openapi.json
tests/
├── api/test_openapi.py
└── integration/
    ├── test_ingredient_routes.py
    ├── test_mcp_ingredients.py
    └── test_mcp_transport.py
```

**Structure Decision**: Extend the current ingredient application service, REST route/schema, and
MCP catalog tool. Exercise the shared page behavior through PostgreSQL-backed integration tests;
verify the generated OpenAPI contract through the existing API contract test and exporter.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | No constitutional violations identified. | Not applicable. |
