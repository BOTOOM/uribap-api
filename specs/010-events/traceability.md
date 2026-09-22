# Traceability: Domain Events and Email Outbox

| Spec item | Artifact | Evidence |
| --- | --- | --- |
| US1 activity feed | FR-006, `GET /households/{id}/activity` | feed + pagination tests |
| US2 atomic emission | FR-002/005/007, `record_event` per mutation | emission tests across services |
| US3 suppression | FR-003/004/008, dispatcher + intents | suppression test, zero-SMTP assertion |
| US4 safe re-dispatch | FR-003, SKIP LOCKED claim | idempotent re-run test |
| US5 observability | FR-001, `request_id` + scrubbed payload | scrubbing + tenant tests |
| OpenAPI | contract paths/schemas | exported `openapi.json` |
