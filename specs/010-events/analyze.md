# Analysis: Domain Events and Email Outbox

## Coverage

| Requirement | Covered by |
| --- | --- |
| FR-001 event schema | T002 |
| FR-002 pure policies | T001 |
| FR-003/004 dispatcher | T001 (decision/backoff), T004 |
| FR-005 emission | T003 |
| FR-006 activity feed | T005 |
| FR-007 atomicity | T003 (same session), T006 (tests) |
| FR-008 no real email | T001 (decision), T004, T006 (SMTP monkeypatch) |

## Consistency checks

- Events are written inside each mutation's existing `session` transaction —
  rollback of the mutation necessarily removes the event; a failed event write
  aborts the mutation (FR-007 both directions).
- `suppressed` is terminal and the dispatcher filters `status = 'pending'`, so
  re-runs are idempotent by construction (SC-003).
- Payload scrubbing reuses the same denylist as `record_audit`; events never
  store emails/tokens — only aggregate ids, kinds, counts, and amounts.
- Feed queries are household-scoped on the member's `household_id`, matching the
  tenant-isolation convention of every other read.
- `email_delivery_enabled=false` means the SMTP path is unreachable; the intent
  row is the audit trail of what delivery would have done.

## Resolved questions

- Outbox rows for `verification`/`password_reset` have no household — intents
  carry nullable `household_id` and the feed only summarizes invitation-kind
  counts per household (dedupe prefix `household-invitation:<id>` joined via
  `household_invitation.household_id`).
