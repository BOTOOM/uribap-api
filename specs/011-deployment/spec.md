# Feature Specification: Deployment Hardening and Operations Runbooks

**Feature Branch**: `011-deployment`  **Status**: Ready for implementation

## User Stories

- **US1 (P1)**: An operator deploys the API to Coolify using a documented
  environment-variable contract and health-check semantics, without guessing
  which settings are required or safe defaults.
- **US2 (P1)**: Every API response carries baseline security headers so the
  service is safe to expose behind a public reverse proxy.
- **US3 (P1)**: The runbook documents migrations as an explicit release step,
  the outbox dispatcher invocation, and the email-delivery-disabled guarantee —
  no undocumented operational behavior.
- **US4 (P2)**: Local development keeps working unchanged — hardening must not
  break `compose.yml` flows or the documented dev ports.

## Requirements

- **FR-001**: API responses MUST include `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and
  `Permissions-Policy` restrictions; `/api/v1` JSON responses additionally get
  `Cache-Control: no-store`. Interactive docs paths (`/docs`, `/redoc`,
  `/openapi.json`) keep working.
- **FR-002**: `.env.example` MUST document every `Settings` field, including
  `EMAIL_DELIVERY_ENABLED=false`, with safe local defaults and no real
  credentials.
- **FR-003**: `docs/operations/coolify.md` MUST document the env-var contract,
  health endpoints (`/api/v1/health/live` and `/ready`), the explicit Alembic
  release step, the outbox dispatcher command, rollback notes, and the
  email-disabled guarantee.
- **FR-004**: Hardening MUST NOT log or expose credentials, tokens, stack
  traces, or personal data in health/headers.
- **FR-005**: No schema, OpenAPI, or domain change in this phase; existing
  tests stay green.

## Acceptance

- `curl -I` on any `/api/v1` route shows the new headers; docs still render.
- A fresh clone with `.env.example` boots `compose.yml` and passes health.
- The runbook lists every env var the image consumes, including the dispatcher.
- All gates in `quickstart.md` pass.

## Edge cases

- `EMAIL_DELIVERY_ENABLED` absent → defaults to `false` (delivery stays off).
- HSTS is intentionally delegated to the TLS-terminating proxy and documented,
  not set by the app (avoids pinning on plain-HTTP local deployments).

## Measurable outcomes

- Header middleware covered by API tests; zero new pyright/Ruff findings;
  `pip-audit` clean; Docker image health unchanged.
