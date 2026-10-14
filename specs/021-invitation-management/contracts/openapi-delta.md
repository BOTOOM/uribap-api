# Contract Delta: Household Invitation Management

Additive, non-breaking changes to the canonical OpenAPI (regenerate `openapi/uribap-api.openapi.json`).

## `InvitationResponse` (extended)

```yaml
InvitationResponse:
  properties:
    id: uuid
    household_id: uuid
    email: string
    requested_role: { enum: [owner, admin, member] }
    status: { enum: [pending, accepted, revoked, expired] }
    effective_status: { enum: [pending, expired, accepted, revoked] }   # NEW — derived
    delivery: { enum: [sent, failed, existing_account, pending], nullable: true }  # NEW — from outbox
    expires_at: date-time
    invited_by_user_id: uuid
    created_at: date-time
```

- `effective_status`: `pending` only while `expires_at > now`; a `pending` row past expiry reports `expired`.
- `delivery`: outbox `sent`→`sent`, `failed`→`failed`, `suppressed`→`existing_account`, `pending`→`pending`, no outbox→`null`.

## Endpoints (unchanged signatures)

- `GET /api/v1/households/{householdId}/invitations` → `InvitationPage` with the extended item (owner/admin only).
- `POST /api/v1/households/{householdId}/invitations` → resend path: `InvitationCreate{email}` against an expired/failed pending invitation returns `202 InvitationCreatedResponse` with the new `delivery`; valid pending still returns `409`.
- `DELETE /api/v1/households/{householdId}/invitations/{invitationId}` → revoke (unchanged).
- `POST /api/v1/invitations/accept`, `GET /api/v1/me/invitations`, `POST /api/v1/me/invitations/{id}/accept` (unchanged).

The web client must pin the regenerated contract snapshot.
