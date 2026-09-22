# Requirements Checklist: Domain Events and Email Outbox

- [x] User stories with priorities
- [x] Functional requirements numbered and testable
- [x] Event catalog + suppression state machine defined
- [x] Tenant isolation on every entity and query
- [x] Idempotent dispatch + payload scrubbing specified
- [x] No-real-email guarantee explicit (FR-008)
- [x] Out-of-scope items explicit (scheduler, real SMTP, webhook fan-out)
