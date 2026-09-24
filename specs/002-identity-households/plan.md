# Implementation Plan: Identity and Households

**Branch**: `002-identity-households` | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification for provider-neutral OIDC validation, internal identity provisioning, households, memberships, invitations, and local identity infrastructure.

## Summary

Implement the first protected Uribap API boundary. The API will validate ZITADEL/OIDC access tokens through an issuer-configured asynchronous JWKS cache, provision an internal user and linked provider identity idempotently, and expose household, membership, invitation, audit, and current-user resources. All tenant-owned access will flow through a composable membership dependency. Local identity acceptance will use a dedicated ZITADEL PostgreSQL volume and Mailpit, with no Brevo or real SMTP credentials.

The implementation remains a modular monolith. SQLAlchemy models and Alembic migrations own persistence; framework-independent identity/authorization policies and invitation token operations are covered by pure tests; FastAPI routes coordinate application services and expose the canonical OpenAPI contract.

## Technical Context

**Language/Version**: Python 3.14.x

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic, psycopg 3, Pydantic Settings, PyJWT with cryptography, httpx, Python standard-library email/smtplib boundary, pytest, pytest-asyncio, HTTPX

**Python Tooling**: UV exclusively (`uv add`, `uv sync --locked`, `uv run`, committed `uv.lock`); no pip or manual virtualenv.

**Storage**: PostgreSQL 18 for Uribap application data; a separate PostgreSQL 17/18-compatible volume for local ZITADEL; no identity-provider data in the application database

**Testing**: pytest unit tests for claims/roles/token hashing; API tests with deterministic JWT fixtures; PostgreSQL integration tests for migrations, constraints, concurrency, outbox, and tenant isolation; local Compose tests against ZITADEL/JWKS/Mailpit; deterministic OpenAPI export; Ruff, Pyright, pip-audit, secret scan

**Target Platform**: Linux Docker container on Coolify; local Docker Compose on a developer workstation; local identity profile available without external SMTP

**Project Type**: Layered modular monolith REST API

**Performance Goals**: Warm JWKS-protected API p95 under 500ms in the local profile; bounded JWKS timeout; one API worker; no blocking network call inside request handling; invitation/membership mutations remain transactionally atomic

**Constraints**: no passwords or provider secrets stored in Uribap; no raw tokens in logs/database; Decimal conventions remain intact; no queues/caches/workers unless justified; application DB and ZITADEL DB isolated; public repository; all migrations reviewed; only synthetic local email addresses

**Scale/Scope**: Initial two-person household, schema supports multiple memberships and practical household sizes; one application database; local identity stack for development and CI-like tests; no production Brevo configuration in this feature

## Constitution Check

- **Domain correctness**: PASS. Identity provisioning, membership, invitation, and audit state are explicit transactional records; no planned domain action mutates inventory.
- **Deterministic services and test-first**: PASS. Claim policy, role policy, token hashing, invitation state transitions, and permission decisions are pure-testable before route integration.
- **Tenant isolation and secure identity**: PASS. Every household-owned query requires an active membership; issuer, audience, signature, expiry, scopes, and subject are validated; secrets/tokens are excluded from logs and persistence.
- **Contract-first API evolution**: PASS. All resources, permission errors, conflict responses, idempotency keys, versions, and pagination are documented in `contracts/identity-households.md` and exported OpenAPI.
- **Resource-aware simplicity**: PASS. The API remains one modular monolith; JWKS uses bounded in-process caching rather than a new service; local identity infrastructure is isolated Compose infrastructure.
- **Auditable operations**: PASS. Alembic migration, append-only audit events, email outbox, Docker healthchecks, dependency scans, and local identity runbook are release gates.

## Research Decisions

See [research.md](./research.md) for the evidence and alternatives. The central decisions are:

1. Use PyJWT with `cryptography` and an asynchronous `httpx` JWKS cache; do not use unbounded synchronous JWKS calls in FastAPI handlers.
2. Use `(issuer, subject)` as the immutable external identity key and keep Uribap user IDs independent of ZITADEL IDs.
3. Use a separate `compose.identity.yml` owned by the API repository as the canonical local stack; Web tests consume the same stack.
4. Use Mailpit as the only local SMTP endpoint; production Brevo remains deployment configuration, not feature code.
5. Use hashed one-time invitation tokens and an atomic consume operation; raw tokens exist only in the local email payload/HTTP request boundary.
6. Enforce tenant access through `require_household_membership` dependencies plus service-level checks, never by trusting a client-provided household claim.

## Model Assignment

- **Primary**: `gpt-5-6-luna-max` for identity/domain architecture and invariant decisions.
- **Implementation**: `gpt-5-6-sol-high` for multi-file API, migration, Compose, and contract implementation.
- **Reviewer**: `gpt-5-6-terra-high` for OIDC/JWT, SQL isolation, concurrency, secrets, and migration review.
- **Artifact analyst**: `glm-5-3-max` for long-context spec/plan/tasks consistency.
- **Routine fixer**: `swe-2-high` for bounded lint/type/test corrections; `swe-2-max` for bounded multi-file fixes.
- **Escalation**: `kimi-k3-max` only for explicit cross-repo artifact review after the normal analysis cannot resolve a material conflict.

## Project Structure

### Documentation (this feature)

```text
specs/002-identity-households/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── traceability.md
├── analyze.md
├── converge.md
├── contracts/
│   └── identity-households.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/uribap_api/
├── api/
│   ├── dependencies.py
│   ├── errors.py
│   ├── identity.py
│   ├── households.py
│   ├── invitations.py
│   ├── router.py
│   └── schemas.py
├── application/
│   ├── identity_service.py
│   ├── household_service.py
│   ├── invitation_service.py
│   └── audit_service.py
├── domain/
│   ├── identity/
│   │   ├── models.py
│   │   ├── policies.py
│   │   └── errors.py
│   └── household/
│       ├── models.py
│       ├── policies.py
│       └── errors.py
├── infrastructure/
│   ├── identity/
│   │   ├── claims.py
│   │   ├── jwks_cache.py
│   │   └── jwt_validator.py
│   ├── database.py
│   ├── email/
│   │   ├── mailer.py
│   │   └── outbox.py
│   ├── logging.py
│   └── persistence/
│       ├── base.py
│       ├── identity_models.py
│       └── household_models.py
└── config.py

migrations/versions/
└── <identity-households migration>.py

tests/
├── unit/
│   ├── domain/test_identity_policies.py
│   ├── domain/test_household_policies.py
│   └── infrastructure/test_jwt_validator.py
├── api/
│   ├── test_identity_routes.py
│   ├── test_household_routes.py
│   └── test_invitation_routes.py
└── integration/
    ├── test_identity_households_db.py
    ├── test_tenant_isolation.py
    ├── test_identity_compose.py
    └── test_mailpit_flows.py

identity/
├── compose.identity.yml
├── .env.identity.example
├── README.md
└── scripts/
    ├── wait-for-identity.sh
    └── seed-local-oidc.py

openapi/openapi.json
```

**Structure Decision**: Keep domain policy independent from FastAPI and persistence. Put canonical local identity infrastructure under `identity/` in the API repository because it coordinates API/JWKS/PostgreSQL/Mailpit and can be referenced by the Web repository without duplicating provider setup.

## Implementation Phases

### Phase 0 — Research and contract design

- Resolve PyJWT/JWKS, ZITADEL Compose, Mailpit, Auth.js boundary, token/cookie, and invitation security decisions.
- Complete data model and API contract.
- Validate constitution gates and local-only secret policy.

### Phase 1 — Foundational security and persistence

- Add settings for issuer/audience/JWKS/scopes, approved algorithms, cache TTL, timeouts, and local email.
- Add SQLAlchemy metadata, Alembic migration, constraints, indexes, audit/outbox records, and safe redaction.
- Add pure JWT/claims/role/invitation policy tests before route implementation.

### Phase 2 — Identity provisioning and authorization (User Story 1)

- Implement asynchronous JWKS cache and JWT validation.
- Add current-user route, identity upsert, scope/role dependencies, 401/403 errors, and transaction tests.

### Phase 3 — Household lifecycle (User Story 2)

- Implement create/read/update household settings, member listing, membership authorization, optimistic concurrency, and isolation tests.

### Phase 4 — Invitations and membership administration (User Story 3)

- Implement invitation outbox/mailer boundary, create/list/revoke/accept flows, role changes, owner invariants, audit events, Mailpit assertions, and concurrency tests.

### Phase 5 — Local identity Compose and release gates

- Add the official-ZITADEL-derived local Compose stack with dedicated PostgreSQL and Mailpit, seed/setup scripts, health checks, sanitized `.env.example`, quickstart, OpenAPI snapshot, security scans, and resource observations.

## Complexity Tracking

No constitution violations. The local identity stack is a separate Compose profile rather than a runtime microservice. The asynchronous JWKS cache is bounded in-process infrastructure required to avoid blocking API handlers and is covered by timeout/rotation tests.

## Deployment Readiness Amendment

Use an optional `OIDC_USERINFO_URL` setting, default empty. A configured URL must share the configured issuer's HTTP(S) origin, contain no credentials/query/fragment, and use HTTPS in production. This intentionally validates the public issuer origin rather than an implicit alternate-provider URL. An explicit `OIDC_USERINFO_CONNECT_HOST=host.docker.internal` transport mapping is permitted only in development/test with an HTTP loopback issuer; it preserves the public Host header and port and is rejected in production. The local Compose file supplies the existing Docker host-gateway mapping. No new dependency, migration, or OpenAPI change is needed.

Add an asynchronous `UserInfoClient` using existing httpx and `OIDC_TIMEOUT_SECONDS`. Disable redirects explicitly. Fetch only after JWT validation and scope enforcement. Require a non-empty matching `sub`; project only `email`, `email_verified`, `name`, and `preferred_username` into the already validated payload. Preserve issuer, audience, expiry, subject, scope, and all authorization decisions. A missing email must never yield verified-email authority. Do not cache bearer tokens or profile responses in this amendment, so verification changes are not hidden by a new cache.

Map provider 401/403 or subject mismatch to redacted 401; transport failures, other statuses including redirects, invalid JSON and invalid profile shapes to redacted 503. Do not expose upstream bodies or tokens in exceptions. Preserve the existing behavior when UserInfo is not configured.

Update the local seed to create JWT rather than opaque tokens, include profile claims in ID tokens, emit OIDC_USERINFO_URL, leave OIDC_REQUIRED_SCOPES empty for stock ZITADEL 4.16 JWTs without a signed scope claim, and write credential output with mode 0600. Existing seeded clients are not silently changed; document the required manual JWT/profile settings. Remove the production runbook recommendation to use the login-client PAT for administrative provisioning. Record where identity versus application email templates are configured, without enabling real delivery. UserInfo provides profile fields only and MUST NOT be used to synthesize scopes; any nonempty required-scope policy remains strict.

Tests first: signed-token cases with and without UserInfo, exact subject binding, strict profile shapes, false/missing verification, unauthorized/outage/timeout/redirect behavior, no profile calls for rejected JWTs/scopes, preserved security claims, URL validation, seed request configuration and file mode. Use deterministic synthetic identities and httpx MockTransport; production issuers and SMTP are forbidden in tests.

Focused gate: Ruff, Pyright, and the new identity/configuration/seed regression tests. Final cross-repository gate adds existing unit/API/integration and OpenAPI checks plus local ZITADEL/Mailpit/Web flow verification where available. Record unavailable checks honestly; unrelated historical tasks are not closed by this amendment.

Model-policy exception: `devin models list --format json` could not authenticate. The user explicitly selected "Usar esta sesión", authorizing the available session models and execution tools for this work. The lead owns architecture/security review; implementation and test execution use the session's available delegated worker. No historical model-availability claim is made.

Follow-up: Align McpToken metadata with the existing named unique constraint and unique index; no database DDL change or new migration. Verify the metadata regression and alembic check on the dedicated test database.
