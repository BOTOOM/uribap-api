# Analyze: Deployment Hardening and Operations Runbooks

## Coverage

- FR-001 → T001 (middleware + header tests).
- FR-002 → T002 (`.env.example` parity with `Settings`).
- FR-003 → T003 (runbook).
- FR-004 → T001 assertions only check presence of static headers; no secrets.
- FR-005 → T004 (unchanged contract/alembic gates).

## Consistency

- No new endpoint or schema → no data-model/contracts artifacts needed; the
  OpenAPI snapshot must stay byte-identical (checked in T004).
- Middleware approach matches the existing `RequestIdMiddleware` pattern.
- Header set chosen to be proxy-agnostic; HSTS documented as proxy-owned.

## Risks → mitigations

- Error-path responses missing headers → middleware outermost; test covers a
  404 response.
- Docs breakage via CSP → no CSP on docs paths; only `nosniff`/frame headers.

## Open questions

None — scope is docs/config/middleware only, deployment itself is out of
scope per the roadmap.
