---
name: uribap-local-identity-testing
description: Run Uribap authentication and household tests against a disposable local ZITADEL, PostgreSQL, and Mailpit Docker Compose stack without external SMTP.
argument-hint: "[identity flow or feature]"
triggers:
  - user
  - model
allowed-tools:
  - read
  - grep
  - glob
  - exec
---

# Uribap Local Identity Testing

This skill is project-local and is loaded by Devin sessions working in `uribap-api`.

Use this skill for `002-identity-households`, `002-oidc-bff-onboarding`, and later features that
need real OIDC behavior. This stack is local-only and must never use production credentials,
Brevo, real email addresses, or a production issuer.

All API-side Python helpers and checks MUST run through UV (`uv run`/`uv sync --locked`); do not
install packages with pip or create a separate manual virtualenv.

## Local stack contract

The local Compose profile must provide:

- ZITADEL API/Login using the official self-hosted Compose setup;
- a dedicated ZITADEL PostgreSQL database/volume, isolated from the Uribap application database;
- Mailpit as the local SMTP capture service for verification/reset/invitation messages;
- documented environment values for Web issuer/client and API issuer/audience validation.

SMTP is optional for basic manually-created login tests. It is required for complete email-flow
coverage; in that case Mailpit is the SMTP endpoint and no external SMTP server is needed.

## Required test flows

1. Start the local identity profile and wait for ZITADEL/PostgreSQL health.
2. Create or seed a disposable test organization/project/application without real secrets.
3. Verify authorization-code + PKCE login and secure callback handling.
4. Verify logout/federated logout and expired/invalid token rejection.
5. Verify Web BFF cookies never expose access/refresh tokens to client JavaScript.
6. Verify API JWKS/issuer/audience/scope validation and tenant membership checks.
7. Trigger verification/reset/invitation emails and inspect Mailpit; assert recipient/subject/link
   without sending anything externally.
8. Tear down only the named local identity containers after preserving logs/test artifacts. Do not
   delete volumes automatically.

## Test boundaries

- Unit tests use deterministic signed test tokens/fixtures and do not require ZITADEL.
- API integration tests validate JWKS and claims against the local issuer.
- Playwright tests use the local OIDC login and Mailpit when an email action is required.
- Production Brevo configuration is tested only in a separately approved deployment environment.

## Completion gate

Report issuer, client/application setup, token/cookie checks, tenant isolation, email capture,
refresh/logout, browser results, Docker health, skipped flows, and any cleanup that requires user
approval. A missing SMTP service may only be reported as a limitation for basic-login tests; it
cannot be called a complete identity-flow pass.
