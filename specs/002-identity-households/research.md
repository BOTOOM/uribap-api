# Research: Identity and Households

**Feature**: `002-identity-households`

**Date**: 2026-09-10

## Decision 1: OIDC validation library and JWKS strategy

- **Decision**: Use PyJWT with the `cryptography` extra for JWT verification and an asynchronous `httpx` JWKS cache with a bounded TTL, timeout, and refresh-on-unknown-key behavior.
- **Rationale**: PyJWT is maintained, supports issuer/audience/expiry validation and JWK conversion, and its documentation covers JWKS retrieval. FastAPI request handlers must not perform unbounded synchronous network I/O. A small async cache keeps the modular monolith simple while making key rotation testable.
- **Alternatives considered**: `python-jose` was not selected because PyJWT has the required JWK/JWKS support with a smaller, explicit surface; hard-coded public keys were rejected because ZITADEL rotates keys; an external cache/service was rejected by the resource-aware simplicity principle.
- **Sources**: [PyJWT](https://pypi.org/project/PyJWT/), [PyJWT JWKS usage](https://pyjwt.readthedocs.io/en/latest/usage.html#retrieve-rsa-signing-keys-from-a-jwks-endpoint).

## Decision 2: Provider-neutral identity key

- **Decision**: Store an internal `app_user` ID and link each external identity by unique `(issuer, subject)`. Treat the issuer and subject as immutable identity keys; email is a profile/verification attribute, not the primary key.
- **Rationale**: OIDC `sub` is only unique within an issuer. This prevents collisions across providers or future ZITADEL instances and avoids account takeover through email changes.
- **Alternatives considered**: Email-only identity was rejected because email can change and may not be verified; provider-specific user IDs were rejected because they couple the domain to ZITADEL.

## Decision 3: Token claims and authorization

- **Decision**: Require configured `iss`, `aud`, approved asymmetric algorithms, `exp`, `sub`, and configured scopes. Resolve household membership from the application database using the internal user ID; never trust a client-provided household claim as authorization.
- **Rationale**: Provider claims authenticate a principal; household membership is Uribap application authorization and must be revocable immediately.
- **Alternatives considered**: Embedding role/household authorization entirely in provider claims was rejected because membership changes would wait for token refresh and would weaken tenant isolation.

## Decision 4: Local ZITADEL Compose

- **Decision**: Keep a dedicated `identity/compose.identity.yml` with ZITADEL's official self-hosted Compose pattern, separate PostgreSQL volume, and Mailpit. Pin the ZITADEL image version in the tracked Compose file and keep first-instance passwords/masterkey in an ignored local `.env` generated from `.env.identity.example`.
- **Rationale**: The official ZITADEL Compose quickstart includes Traefik, ZITADEL API/Login, and PostgreSQL and supports `docker compose up -d --wait`. A separate named project/volume avoids collisions with Uribap's application database. First-instance environment variables are only applied on the first volume initialization, which must be explicit in the runbook.
- **Alternatives considered**: Using ZITADEL Cloud was rejected for local/CI determinism; sharing the Uribap application PostgreSQL volume was rejected for isolation; hand-written mock OIDC was rejected because it cannot validate real JWKS/PKCE behavior.
- **Source**: [ZITADEL Docker Compose](https://zitadel.com/docs/self-hosting/deploy/compose).

## Decision 5: Local email capture

- **Decision**: Configure the local ZITADEL SMTP provider and Uribap notification boundary to use `mailpit:1025` without authentication; expose only Mailpit UI on `localhost:8025` for inspection. No Brevo credentials or external SMTP host may appear in local files.
- **Rationale**: Mailpit accepts local synthetic messages and exposes an API/UI for assertions. It provides complete verification, reset, and invitation flow coverage without sending real email.
- **Alternatives considered**: Omitting SMTP was accepted only for basic login tests; it is insufficient for complete identity-flow acceptance. Brevo was rejected for local development because it introduces real delivery and credential risk.
- **Sources**: [ZITADEL notification providers](https://zitadel.com/docs/guides/manage/customize/notification-providers), [Mailpit Docker](https://mailpit.axllent.org/docs/install/docker/).

## Decision 6: Invitation security

- **Decision**: Generate a high-entropy opaque invitation token, store only a cryptographic hash, send the raw token only through the local/production email boundary, expire it, and consume it atomically under a row lock or compare-and-set update. API responses never return the raw token.
- **Rationale**: Hashing limits database exposure; atomic consumption handles retries/concurrency; verified-email matching prevents forwarding abuse.
- **Alternatives considered**: Persisting raw tokens was rejected; JWT invitations were rejected because revocation and one-time consumption are harder; accepting by email without a token was rejected because it is not a possession-bound invitation.

## Decision 7: Audit and email outbox

- **Decision**: Record membership/invitation security actions in an append-only audit table and durable notification intent in an email outbox table. The first implementation sends through a bounded SMTP adapter in the same application boundary; retries are idempotent by outbox key.
- **Rationale**: The project needs auditable security actions but does not yet justify a worker/queue. A durable boundary allows later asynchronous delivery without changing domain semantics.
- **Alternatives considered**: Direct untracked SMTP sends were rejected because failures and retries would be opaque; introducing Celery/Redis was rejected as unnecessary infrastructure for the initial household scale.

## Decision 8: Error and concurrency contract

- **Decision**: Use the existing Problem Details envelope with stable codes: `unauthorized`, `forbidden`, `not_found`, `validation_error`, `conflict`, `invitation_expired`, `invitation_consumed`, and `identity_provider_unavailable`. Use `If-Match`/version fields for household settings and idempotency keys for mutations where retry duplication is possible.
- **Rationale**: This preserves the foundation contract, lets Web distinguish permission/state outcomes, and makes retries explicit.
- **Alternatives considered**: Generic 500 responses were rejected; silently last-write-wins settings were rejected because household administration needs predictable conflict behavior.

## Decision 9: Auth.js/Web integration boundary

- **Decision**: The Web feature uses Auth.js's built-in ZITADEL provider and server-side session callbacks. The API remains the authority for internal user and household membership; Web session data contains only safe user/membership summaries.
- **Rationale**: Auth.js documents a ZITADEL provider and local callback URI for Next.js. Auth.js manages state/nonce/PKCE and encrypted HttpOnly session cookies while server-only code forwards access tokens to the API.
- **Source**: [Auth.js ZITADEL provider](https://authjs.dev/getting-started/providers/zitadel), [ZITADEL Next.js example](https://zitadel.com/docs/sdk-examples/nextjs).
