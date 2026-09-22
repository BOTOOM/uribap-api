# Implementation Plan: Domain Events, Email Outbox, and Observability

## Stack layers

1. **Spec** — this artifact set.
2. **Domain** — pure policies in `domain/events/policies.py`: `DomainEventKind`
   catalog, payload scrubbing (shared denylist with audit), delivery decision
   (`suppressed` vs `send`), and capped exponential backoff. Unit tests first.
3. **Persistence** — `event_models.py` (`domain_event`,
   `email_delivery_intent`), migration adding both tables, widening the
   `email_outbox_entry` status CHECK to include `suppressed`, and
   `uq_domain_event_household`; schema integration tests.
4. **Service** — `event_service.py` (`record_event`, activity feed, outbox
   dispatcher claiming with `FOR UPDATE SKIP LOCKED`), event emission wired into
   household/invitation/planning/shopping/preparation/completion services,
   `api/event_schemas.py` + `GET /households/{id}/activity`, config flag
   `email_delivery_enabled` (default `false`), integration + route tests,
   OpenAPI export.

## Key decisions

- `domain_event` is the business-event log (what happened); `audit_event` stays
  the security trail (who did it, request-scoped). Events carry scrubbed
  aggregate references only — no emails, tokens, or free text.
- Suppression is terminal and intentful: every claim writes an
  `email_delivery_intent` so operators can audit *what would have been sent*
  without any SMTP traffic.
- The dispatcher is a service function plus a thin CLI entry
  (`uv run python -m uribap_api.tools.process_outbox`) — no HTTP endpoint, no
  scheduler in this phase.
- `email_delivery_enabled=false` is the default and the only tested mode; the
  SMTP path stays behind the flag for phase 011+.
- Emission is inlined in each mutation's existing transaction (same `session`),
  satisfying FR-002/FR-007 with no new infrastructure.

## Models

- Architecture: `gpt-5-6-luna-max`; implementation: `gpt-5-6-sol-high`;
  transaction/security review: `gpt-5-6-terra-high`; bounded fixes: `swe-2-high`.
