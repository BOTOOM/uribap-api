# Traceability: Shopping

| Requirement | Evidence/task |
|---|---|
| FR-001 tenant isolation + version | T003/T004/T005/T006 |
| FR-002 generation from 006 shortfall | T006/T007, projection reuse tests |
| FR-003 item fields + open-only mutation | T003/T004/T006 |
| FR-004 atomic purchase lot+movement+item | T006/T007 |
| FR-005 item transitions | T002/T003, pure tests |
| FR-006 list transitions + zero-pending rule | T002/T003/T007 |
| FR-007 expected_version/409 | T002/T005/T007 |
| FR-008 idempotent replay incl. purchase | T005/T007 |
| FR-009 composite FKs + lot household | T004/T005 |
| FR-010 Problem Details | T006/T008, OpenAPI |
| FR-011 unique live window | T004/T005 |
| FR-012 no plan mutation / no email | spec/plan scope, constitution review |
