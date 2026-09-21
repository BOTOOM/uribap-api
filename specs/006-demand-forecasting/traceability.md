# Traceability: Demand Forecasting

| Requirement | Evidence/task |
|---|---|
| FR-001 approved-only window source | T003/T004/T005, service + integration tests |
| FR-002 Decimal serving scaling | T002/T003, pure policy tests |
| FR-003 per-(ingredient,unit) aggregation | T002/T003/T005 |
| FR-004 required/optional split | T002/T003 |
| FR-005 on-hand availability rule | T004/T005, lot filter tests |
| FR-006 shortfall + zero-line suppression | T002/T003 |
| FR-007 read-only, no idempotency | T004/T005, no-write test |
| FR-008 window defaults + 62-day cap | T003/T005 |
| FR-009 echoed window + plan ids | T004/T005 |
| FR-010 deterministic payload | T005, repeated-request test |
| FR-011 Problem Details | T004/T006, OpenAPI |
| FR-012 no shopping/prep/consumption | spec/plan scope, constitution review |
| Out-of-scope email/deployment | plan, quickstart, constitution review |
