# Tasks: Deployment Hardening and Operations Runbooks

## Implementation

- T001 `SecurityHeadersMiddleware` + registration; API tests for headers on
  `/api/v1` responses (incl. error responses) and reachable docs paths.
- T002 `.env.example` completeness pass — `EMAIL_DELIVERY_ENABLED=false` and
  every `Settings` field documented with safe local defaults.
- T003 `docs/operations/coolify.md` runbook: env table, health semantics,
  explicit migration step, outbox dispatcher, rollback, resource baseline,
  security-header rationale, email-disabled guarantee.

## Verify

- T004 Full gates: ruff, format, pyright, full pytest suite, OpenAPI check,
  alembic check (no drift), pip-audit, Docker build + health probe.
