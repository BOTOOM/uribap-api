# Traceability: Meal Completion

| Spec item | Artifact | Evidence |
| --- | --- | --- |
| US1 complete + FEFO | spec FR-002/003, contract `POST /plans/{}/entries/{}/complete` | domain + service tests |
| US2 planned vs actual | FR-004, `MealCompletionLineResponse` | schema tests, GET endpoints |
| US3 correction | FR-005, `POST .../correct` | reversal + consumption movements test |
| US4 reopen | FR-006, `POST .../reopen` | reversal test, re-completion test |
| US5 idempotency | FR-007, `completion_operation` | replay tests |
| Tenant isolation | FR-001/008 | composite FKs, household filters, cross-tenant tests |
| OpenAPI | FR-009 | exported `openapi.json` |
