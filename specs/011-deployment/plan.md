# Plan: Deployment Hardening and Operations Runbooks

## Architecture

- `infrastructure/security_headers.py` — ASGI middleware applying baseline
  headers to every response; `/api/v1/*` also gets `Cache-Control: no-store`;
  docs paths (`/docs`, `/redoc`, `/openapi.json`) skip CSP-style restrictions.
- `main.py` — register the middleware before CORS so headers survive CORS
  preflights.
- `.env.example` — add `EMAIL_DELIVERY_ENABLED=false` and any missing
  `Settings` fields with safe local values.
- `docs/operations/coolify.md` — deployment runbook: env table, health
  semantics, explicit migration step (`uv run alembic upgrade head`), outbox
  dispatcher (`uv run python -m uribap_api.tools.process_outbox`), rollback,
  resource baseline, security-header rationale (HSTS delegated to proxy).

## Model

`gpt-5-6-sol-high` implementation; `gpt-5-6-terra-high` header/runbook review.

## Testing

- API test: security headers present on a `/api/v1` route and docs paths still
  reachable; `no-store` on API responses.
- Env test: `Settings()` defaults `email_delivery_enabled` to `False`.
- Full suite + OpenAPI check unchanged (54+1 paths).

## Risks

- Header middleware ordering vs. CORS/exception handlers → place middleware
  outermost-enough that error responses also carry headers.
- Docs UIs load CDN assets → do not set CSP `default-src 'none'` on docs paths.
