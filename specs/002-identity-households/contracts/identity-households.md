# Identity and Households API Contract

**Base path**: `/api/v1`

**Authentication**: `Authorization: Bearer <OIDC access token>` for protected operations. The API validates issuer, audience, signature, expiry, subject, and configured scopes. It never accepts a client-provided household role as authority.

**Errors**: `application/problem+json` using the foundation fields `type`, `title`, `status`, `detail`, `instance`, `code`, and `requestId`. Details never contain tokens, secrets, or invitation values.

## `GET /me`

Returns the authenticated internal user and safe active memberships.

- `200`: `{ id, displayName, email, emailVerified, memberships[] }`
- `401 unauthorized`: missing/invalid/expired token.
- `403 forbidden`: valid identity disabled or missing required scope.

Repeated calls for the same `(issuer, subject)` are idempotent.

## `POST /households`

Creates a household and owner membership for the authenticated caller.

Headers:

- `Idempotency-Key`: required for mutation retry safety.

Body:

```json
{
  "name": "Casa Botom",
  "locale": "es",
  "timezone": "Europe/Madrid"
}
```

- `201`: household resource plus caller membership.
- `400 validation_error`: invalid name/locale/timezone.
- `401`, `403`: auth failure.
- `409 conflict`: idempotency mismatch or policy conflict.

## `GET /households/{household_id}`

Returns household settings only when the caller has active membership.

- `200`: `{ id, name, locale, timezone, status, version, createdAt, updatedAt }`
- `401`: unauthenticated.
- `403`: no active membership.
- `404`: the API may use not-found semantics that do not reveal another tenant.

## `PATCH /households/{household_id}`

Updates allowed settings using optimistic concurrency.

Headers:

- `If-Match`: current integer version, required.
- `Idempotency-Key`: required for mutation retry safety.

Body fields are optional: `name`, `locale`, `timezone`.

- `200`: updated household with incremented version.
- `400`: validation error.
- `403`: insufficient role.
- `409 conflict`: stale version or idempotency mismatch.

## `GET /households/{household_id}/members`

Returns a paginated member list with safe profile fields, role, status, and versions.

Query: `cursor`, `limit` (bounded to 100).

- `200`: `{ items[], pageInfo }`
- `403`: no active membership.

## `PATCH /households/{household_id}/members/{user_id}`

Owner/admin role change for an existing member.

Headers: `If-Match`, `Idempotency-Key`.

Body: `{ "role": "admin" | "member" }`.

- `200`: updated membership.
- `403`: caller cannot administer target or would violate owner invariant.
- `404`: safe not-found.
- `409`: stale membership version or idempotency conflict.

## `DELETE /households/{household_id}/members/{user_id}`

Revokes a membership. The last active owner cannot be revoked.

Headers: `If-Match`, `Idempotency-Key`.

- `204`: revoked.
- `403`: insufficient permission or last-owner policy.
- `409`: stale version.

## `GET /households/{household_id}/invitations`

Owner/admin-only paginated list. Raw tokens are never returned.

- `200`: `{ items: [{ id, email, requestedRole, status, expiresAt, invitedBy, createdAt }], pageInfo }`
- `403`: member or non-member.

## `POST /households/{household_id}/invitations`

Creates or resends a one-time invitation and a notification outbox entry.

Headers: `Idempotency-Key`.

Body:

```json
{
  "email": "synthetic-member@example.test",
  "role": "admin" | "member",
  "expiresInHours": 72
}
```

- `202`: invitation metadata and notification status; raw token omitted.
- `400`: invalid email/role/expiry.
- `403`: caller not owner/admin.
- `409`: existing membership or conflicting pending invitation.

## `POST /invitations/accept`

Consumes a raw invitation token supplied by the signed-in recipient. The raw value is accepted only in the request body and is never returned or logged.

Body:

```json
{ "token": "opaque-one-time-token" }
```

- `200`: accepted membership and household summary.
- `400 invitation_expired`: expired or malformed token.
- `403 forbidden`: caller is not signed in, email is not verified/matching, or policy rejects it.
- `409 invitation_consumed`: already accepted/revoked or membership conflict.

## `GET /health/identity`

Local/test diagnostic only; returns provider readiness without exposing secrets. Production exposure is disabled unless explicitly configured.

- `200`: issuer configured, JWKS reachable/cached, required scopes configured.
- `503 identity_provider_unavailable`: provider/JWKS unavailable.

## Security and headers

- `x-request-id` is accepted/generated and returned.
- `ETag`/version and `If-Match` are used for settings/membership concurrency.
- Bearer tokens and invitation token values are redacted from structured logs.
- CORS remains explicit; no wildcard credentials.
- OpenAPI schemas distinguish `401`, `403`, `404`, `409`, and `503` outcomes.
