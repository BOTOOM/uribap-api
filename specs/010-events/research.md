# Research: Domain Events and Email Outbox

## Findings

- `email_outbox_entry` already persists intents (`dedupe_key`, `kind`,
  `template_data`, `status`, `attempts`, `available_at`) with helpers
  `queue_email`/`mark_sent`/`mark_failed`; its CHECK only allows
  `pending|sent|failed` — `suppressed` needs a migration widening.
- `mailer.py` performs real SMTP and is only called by no code path today —
  `send_outbox_entry` exists but is unwired; gating it behind
  `email_delivery_enabled` keeps phase 010 send-free.
- `audit_event` + `record_audit` (request_id, actor, scrubbed metadata) already
  covers the security trail in household/invitation services; planning,
  shopping, preparation, and completion mutations emit nothing — the domain
  event feed fills that gap atomically.
- `RequestIdMiddleware` + `get_request_id()` give every service the correlation
  id needed on `domain_event.request_id`.
- Inventory movements show the tenant-safe composite-FK convention
  (`uq_*_household` on parent, composite FK on child) reused for
  `email_delivery_intent` → `email_outbox_entry` is cross-tenant-safe only if
  the intent rows carry `household_id` denormalized — outbox rows are not
  household-scoped (verification/reset kinds), so intents carry
  `household_id NULL` and feed joins happen through `kind`/`dedupe_key`.
- The existing pagination convention is `page`/`page_size` with `has_more`
  (shopping lists, completions) — the activity feed reuses it.

## Decisions

- `domain_event` is append-only, household-scoped, written inside each mutation
  transaction (FR-002 atomicity by construction, no listeners/async).
- Suppression is terminal (`suppressed`, no retry); intents make suppression
  auditable including the rendered subject but not the raw token/link.
- Dispatcher claims with `FOR UPDATE SKIP LOCKED` + batch limit so future
  workers can run concurrently.
- Emission is a small helper (`record_event`) called explicitly per mutation —
  deterministic, testable, and impossible to fire on rollback.
