# Tasks: Domain Events, Email Outbox, and Observability

## Domain

- T001 Event policies: `DomainEventKind` catalog, payload scrubbing, delivery
  decision (`suppressed`/`send`), capped backoff — with unit tests first.

## Persistence

- T002 `domain_event` + `email_delivery_intent` models, migration widening the
  outbox status CHECK to `('pending','sent','failed','suppressed')`,
  `uq_domain_event_household`; schema integration tests.

## Service/API

- T003 `event_service.record_event` + wire emission into household, invitation,
  planning (approve/reopen), shopping (purchase), preparation (complete/cancel),
  and completion (complete/reopen/correct) mutations — same transaction.
- T004 Outbox dispatcher: claim pending rows (`available_at <= now`,
  `FOR UPDATE SKIP LOCKED`), apply delivery decision, write
  `email_delivery_intent`, update status/attempts; CLI entry
  `tools/process_outbox.py`; `email_delivery_enabled` config flag.
- T005 `GET /households/{household_id}/activity` — paginated newest-first event
  feed + outbox status summary; schemas, route, Problem Details.
- T006 Integration + route tests (emission atomicity, suppression without SMTP,
  dispatcher idempotency/backoff, feed pagination, tenant isolation);
  OpenAPI export.
