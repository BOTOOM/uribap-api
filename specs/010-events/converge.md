# Converge: Domain Events, Email Outbox, and Observability

## Scope delivered

- `domain/events/policies.py` — `DomainEventKind` catalog
  (`household.member_*`, `invitation.*`, `plan.approved`/`reopened`,
  `shopping.purchased`, `preparation.task_*`, `meal.*`), payload scrubbing that
  drops sensitive keys and non-scalar values, the delivery decision
  (`send` vs `suppressed` when `email_delivery_enabled` is false), and a capped
  exponential retry backoff (30s → 60s → 120s → … ≤ 1h, exponent capped to
  avoid overflow).
- `infrastructure/persistence/event_models.py` + migration `c1f4a7e2b908` —
  `domain_event` (household-scoped, JSONB payload, `uq_domain_event_household`,
  occurred-at index), `email_delivery_intent` (outcome + attempt detail), and
  the `email_outbox_entry` status CHECK widened to include `suppressed`.
- `application/event_service.py` — `record_event` writes scrubbed payloads in
  the caller's transaction; `list_activity` returns the tenant-scoped
  newest-first feed plus the outbox status summary.
- Emission wired into every mutating service inside the same transaction:
  household create/revoke (`member_added`/`member_removed`), invitation
  create/accept/revoke, plan approve/reopen, shopping purchase, preparation
  complete/cancel, completion complete/reopen/correct.
- `tools/process_outbox.py` — claims pending rows (`available_at <= now`,
  `FOR UPDATE SKIP LOCKED`), applies the delivery decision, writes an
  `EmailDeliveryIntent`, and marks entries `suppressed` without touching SMTP
  when delivery is disabled; suppressed rows are never reclaimed.
- `GET /households/{household_id}/activity` — paginated feed + `OutboxSummary`
  in `api/event_schemas.py`; registered in `api/households.py` with documented
  Problem Details; OpenAPI regenerated.

## Verification

All gates in `quickstart.md` pass, including the full suite (`192 passed,
3 skipped`) against a clean PostgreSQL `uribap_ci` at head `c1f4a7e2b908` with
zero `alembic check` drift; pyright and Ruff clean; `pip-audit` clean; Docker
image boots and serves `/api/v1/health/live`.

## Design notes

- Events persist in the same transaction as their mutation — a rolled-back
  mutation leaves no orphaned event.
- Payloads carry stable references only (IDs, enum values, bounded metadata);
  free-form user text such as preparation task titles is excluded.
- `suppressed` is a terminal outbox state recorded with an intent row, so the
  audit trail shows the notification existed and delivery was disabled — no
  SMTP client is ever constructed in that path.
- The feed is read-only and tenant-scoped through `require_household_membership`;
  the API remains authoritative for activity and delivery state.

## Remaining work

None for API phase 010. Web phase 010 consumes the `v10` contract.
