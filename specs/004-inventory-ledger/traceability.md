# Traceability: Inventory Ledger

| Requirement | Evidence/task |
|---|---|
| FR-001 Decimal finite non-negative balance | T002/T003, domain policy tests, migration checks |
| FR-002 append-only movements | T004/T005, PostgreSQL protection and integration tests |
| FR-003 movement types | T003/T006, OpenAPI enum |
| FR-004 no-negative adjustment | T002/T005/T006, locking test |
| FR-005 tenant isolation | T005/T006, composite FK and authorization tests |
| FR-006 operation-scoped idempotency | T002/T005/T006, request hash/result replay tests |
| FR-007 location/unit dimensions | T003/T006, schema and service validation |
| FR-008 Problem Details | T006/T007, API contract tests |
| Out-of-scope email/deployment | plan, quickstart, constitution review |
