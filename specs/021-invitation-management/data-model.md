# Data Model: Household Invitation Management

## Entities (existing — no schema changes)

### HouseholdInvitation
- `id` (uuid, pk), `household_id` (fk), `invited_email`, `requested_role` (`owner|admin|member`),
  `token_hash`, `status` (`pending|accepted|revoked|expired`), `expires_at`,
  `invited_by_user_id`, `created_at`, `version`, `reminder_sent_at`
- Transitions: `pending → accepted` (invite accept), `pending → revoked` (owner revoke),
  `pending → expired` (lazy: marked on a failed accept attempt). A `pending` row whose
  `expires_at` has passed is *effectively expired* even while the stored status stays `pending`
  until something resolves it.

### EmailOutboxEntry (delivery record)
- `dedupe_key` = `household-invitation:{invitation.id}` (1:1 link)
- `status` (`pending|sent|failed|suppressed`), `recipient_email`, `template_data`

## Derived fields (contract-level, not stored)

- `effective_status`: `accepted` / `revoked` / `expired` as stored, but a `pending` row with
  `expires_at <= now` reports `expired`; otherwise `pending`.
- `delivery`: mapped from the outbox `status` — `sent` → `sent`, `failed` → `failed`,
  `suppressed` → `existing_account` (the invited email already had an account), `pending` → `pending`,
  missing row → `null`.

## Validation rules (from spec)

- List/resend/revoke require owner or admin membership (tenant isolation).
- Resend only has an effect on `expired` effective status or `delivery=failed`;
  `create_invitation` enforces this server-side (409 on valid pending).
- Resend renews the same row (new `token_hash`, fresh `expires_at`), never a duplicate.
- Raw tokens never leave the service; `token` appears only in the delivery payload.
