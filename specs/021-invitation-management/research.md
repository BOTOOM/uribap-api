# Research: Household Invitation Management

## Decision: expose delivery outcome on the existing list endpoint

- **Decision**: extend `InvitationResponse` with `delivery` (from the linked `EmailOutboxEntry.status`) and a derived `effective_status` (`pending` | `expired` | `accepted` | `revoked`), computed from `status` + `expires_at`.
- **Rationale**: the stored status never flips expired rows, so "effective state" must be derived; the owner needs the outbox state to see failed deliveries vs suppressed (existing account) vs sent. One additive contract change, no migration.
- **Alternatives considered**: a separate per-invitation delivery endpoint (extra round-trip, rejected); flipping stored status to EXPIRED lazily on read (side effect in a GET, rejected).

## Decision: resend = re-invite, not a new endpoint

- **Decision**: the web client resends by calling the existing `POST /households/{id}/invitations` with the invitation's email; `create_invitation` already renews expired pendings and retries FAILED outbox entries (PR #158). No new route.
- **Rationale**: the renewal path already regenerates the token, extends expiry, re-locks and redelivers the outbox, and never duplicates rows — every resend guarantee in FR-004..FR-008 for free.
- **Alternatives considered**: `POST /invitations/{id}/resend` (more RESTful but duplicates `create_invitation` logic and request_id semantics; rejected for simplicity). Note: resend needs the invited email — already in the list response.

## Decision: effective-state derivation location

- **Decision**: derive `effective_status` in the response mapping (`invitation_response`), not in SQL.
- **Rationale**: deterministic pure function; keeps `list_invitations` unchanged. Delivery lookup joins `EmailOutboxEntry` by `dedupe_key = household-invitation:{id}` — one extra query or a batched select; fine at ≤100 rows (Principle VI).

## Decision: actionable gating is a client concern

- **Decision**: the API returns raw `status`, `expires_at`, `delivery`, `effective_status`; the web client decides which rows offer Resend (expired or delivery=failed) and Revoke (effective pending). The 409 path in `create_invitation` remains the server-side guard.
- **Rationale**: display logic in the client keeps the contract stable; server rules stay as today.

## Open integration note

`GET /me/invitations` (invitee side) is unchanged; after a resend of an `existing_account` invitation the invitee sees it again — already covered by the merged test in PR #159.
