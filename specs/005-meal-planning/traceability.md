# Traceability: Meal Planning

| Requirement | Evidence/task |
|---|---|
| FR-001 tenant isolation + version | T003/T004/T005, models, service locking tests |
| FR-002 expected_version/409 | T002/T005/T006, concurrency tests |
| FR-003 state machine | T002/T003, pure transition tests |
| FR-004 entry validity | T003/T006, schema/service tests |
| FR-005 no inventory mutation | T002/T005, domain boundary test |
| FR-006 append-only state events | T004/T005, trigger + integration tests |
| FR-007 idempotency replay | T002/T005/T006, receipt/hash tests |
| FR-008 Problem Details | T006/T007, contract tests + OpenAPI |
| FR-009 composite FKs | T004/T005, migration/schema tests |
| FR-010 unique active plan per week | T004/T005, partial unique index test |
| FR-011 no forecasting | plan/spec scope, constitution review |
| Out-of-scope email/deployment | plan, quickstart, constitution review |
