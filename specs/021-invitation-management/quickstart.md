# Quickstart: Household Invitation Management

## Prerequisites

- `docker compose up -d db` (PostgreSQL 18 on :5432), `uv run alembic upgrade head`.

## Validate

```bash
uv run pytest tests/integration/test_invitation_flows.py -q
uv run ruff check && uv run ruff format --check
uv run python -m uribap_api.tools.openapi_export   # regenerate canonical OpenAPI, diff contracts delta
```

## Scenarios covered by tests

1. List shows `effective_status` + `delivery`: seeded invitations in pending/expired/accepted/revoked +
   outbox sent/failed/suppressed/none → each row reports the derived state and delivery outcome.
2. Resend: `POST` to an expired invitation → `202`, new expiry, `token_hash` rotated (FR-004..006);
   `POST` to a valid pending invitation → `409` (FR-009).
3. Existing-account resend: suppressed delivery stays `existing_account`, invitee accepts via
   `/me/invitations/{id}/accept` (covered in PR #159 test).
4. Authorization: non-owner/admin gets 403 on list (FR-003).
5. Revoke: pending → revoked; accept afterwards fails (FR-010).

## Manual smoke (deployed)

Owner signs in → household settings → invitations list shows states → resend an expired one →
invitee accepts (existing account) or receives email.
