# Data Model: Domain Events and Email Outbox

## domain_event

`id`, `household_id` FK NOT NULL, `kind` String(64), `actor_user_id` FK
nullable, `aggregate_type` String(64) NOT NULL, `aggregate_id` UUID nullable,
`payload` JSONB NOT NULL default `{}`, `request_id` String(128) NOT NULL,
`occurred_at` DateTime(tz) NOT NULL, `created_at` server_default.

Constraints/indexes:

- `uq_domain_event_household` on `(id, household_id)`.
- Index `(household_id, occurred_at DESC)` for feed reads.
- Index `(household_id, kind)` for filtered reads.
- CHECK `length(btrim(kind)) > 0`, `length(btrim(aggregate_type)) > 0`.

## email_delivery_intent

`id`, `email_outbox_entry_id` FK NOT NULL, `household_id` FK nullable
(denormalized when the intent is household-bound, else NULL), `outcome`
(`sent`/`suppressed`/`failed`), `subject` String(200) NOT NULL,
`detail` Text nullable, `attempt_number` int >= 1, `created_at` server_default.

Constraints/indexes:

- CHECK `outcome` value set, `attempt_number >= 1`, non-empty `subject`.
- Index `(email_outbox_entry_id, created_at)`.

## email_outbox_entry (existing, altered)

- CHECK `status` widened to `('pending','sent','failed','suppressed')`.
- `suppressed` is terminal: dispatcher never re-claims it.
