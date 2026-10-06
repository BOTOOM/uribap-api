# Analysis — 019 Pantry Staple Ingredients

## Specification Analysis Report

| ID | Category | Severity | Location | Summary | Resolution |
|---|---|---|---|---|---|
| A1 | Completion edge case | HIGH | FR-005–FR-007, completion contract | Filtering all staple lines can otherwise be confused with an empty recipe and trigger the existing empty-consumption error. | Specify separate behavior: zero recipe rows retain the error; one or more all-staple rows complete with zero lines. Add domain and PostgreSQL regressions. |
| A2 | Completion input validation | HIGH | FR-007 | Filtering staples before matching explicit actual lines could produce only a generic unmatched-line error. | Detect staple IDs before line application and return the exact requested 422 detail. |
| A3 | Forecast projection | MEDIUM | FR-009–FR-010 | Excluding staples from forecast demand would hide them from shopping, while partial-stock behavior could create unwanted shortages. | Keep demand totals unchanged; use the zero-on-hand threshold only for staple shortfall. |
| A4 | Plan detail allocation | MEDIUM | FR-011 | A staple row must not consume the shared stock balance even though it reports on-hand stock. | Keep staple on-hand informational and leave the shared allocation balance unchanged. |

## Coverage Summary

| Requirement | Planned coverage |
|---|---|
| FR-001 / FR-013 — persisted default and reversible migration | T006, T010, T016 |
| FR-002 / FR-003 — REST fields and global 403 | T005, T009–T011 |
| FR-004 — MCP create/update/list and descriptions | T008, T011 |
| FR-005–FR-008 — completion filtering, empty/all-staple distinction, exact error, lifecycle | T003, T007, T012 |
| FR-009–FR-010 — forecast fields, staple and non-staple shortfalls, shopping compatibility | T002, T007, T013 |
| FR-011 — entry detail fields and shared stock allocation | T004, T014 |
| FR-012 — generated OpenAPI | T009, T015 |
| SC-001–SC-006 — REST/MCP, completion, forecast, detail, migration, contract | T002–T017 |

## Constitution Alignment

- Domain math stays framework-independent and uses `Decimal`.
- API services remain authoritative for completion, forecast, and detail semantics.
- Tenant boundaries and global ingredient immutability remain enforced by the existing service.
- Domain and integration regressions precede behavior changes.
- Migration is reversible, and OpenAPI is generated from the final API schemas.

## Unmapped Tasks

None. Every requirement maps to one or more domain, integration, migration, contract, or
verification tasks.

## Metrics

- Functional requirements: 13.
- Success criteria: 6.
- High-severity design ambiguities remaining: 0.
- Product implementation is complete; focused and project-level verification passed.
