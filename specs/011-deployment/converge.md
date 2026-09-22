# Converge: Deployment Hardening and Operations Runbooks

## Scope delivered

- `infrastructure/security_headers.py` — `SecurityHeadersMiddleware` sets
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: no-referrer`, and `Permissions-Policy` on every response
  (including Problem Details error responses); `/api/*` additionally gets
  `Cache-Control: no-store` and `Content-Security-Policy: default-src 'none';
  frame-ancestors 'none'`. Docs paths (`/docs`, `/openapi.json`) stay
  functional — no CSP there.
- `main.py` — middleware registered inside CORS so error and CORS responses
  still carry headers.
- `.env.example` — `EMAIL_DELIVERY_ENABLED=false` documented; the file now
  covers every `Settings` field with safe local placeholders.
- `docs/operations/coolify.md` — runbook covering the full env-var contract,
  health semantics, the explicit `alembic upgrade head` release step, the
  outbox dispatcher command and its suppressed-intent guarantee, rollback
  guidance, security-header rationale (HSTS delegated to the proxy), and the
  resource baseline.

## Verification

All gates in `quickstart.md` pass: `196 passed, 3 skipped` against `uribap_ci`
at head `c1f4a7e2b908` with zero `alembic check` drift; ruff/format/pyright
clean; `export_openapi --check` byte-identical; `pip-audit` clean; Docker
image builds and serves `/api/v1/health/live` 200 with all new headers
verified via `curl -i`.

## Design notes

- Middleware sits innermost-under-CORS: preflights are handled by CORS while
  real and error responses flow through the header middleware.
- No CSP on docs paths — Swagger/Scalar load CDN assets and would break.
- `EMAIL_DELIVERY_ENABLED=false` remains the default and is now documented;
  nothing in this phase opens SMTP.

## Remaining work

None for API phase 011. Actual Coolify deployment stays out of scope.
