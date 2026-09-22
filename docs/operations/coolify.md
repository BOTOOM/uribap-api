# Coolify Operations Runbook

This document describes how the API image is configured and operated on a
Coolify-style Docker deployment. Deployment itself is out of scope for this
phase — this runbook is the contract a future deploy must satisfy.

## Build

- Coolify deploys `Dockerfile` at the repository root (multi-stage, non-root
  `appuser`, uv-locked `uv sync --frozen --no-dev`).
- The image `CMD` only starts Uvicorn; migrations are NOT applied
  automatically on boot (that is the dev `compose.yml` behavior only).

## Environment contract

Every setting maps to an environment variable consumed by `Settings`
(`src/uribap_api/config.py`). Required for production:

| Variable | Purpose | Production notes |
| --- | --- | --- |
| `ENVIRONMENT` | `development`/`test`/`production` | `production` — rejects localhost `DATABASE_URL` |
| `DATABASE_URL` | SQLAlchemy URL | managed Postgres DSN; never localhost |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` / `DATABASE_POOL_TIMEOUT_SECONDS` | pool tuning | defaults 5/5/5s |
| `OIDC_ISSUER` / `OIDC_AUDIENCE` | token validation | ZITADEL issuer URL + API audience |
| `OIDC_JWKS_URL` / `OIDC_JWKS_HOST` / `OIDC_ALGORITHMS` | JWKS resolution | `RS256`; host override for internal DNS |
| `OIDC_REQUIRED_SCOPES` / `OIDC_JWKS_TTL_SECONDS` / `OIDC_TIMEOUT_SECONDS` / `OIDC_CLOCK_SKEW_SECONDS` | token policy | defaults sane |
| `CORS_ORIGINS` | allowed web origins | comma-separated; the Vercel app origin only |
| `WEB_BASE_URL` | links in outbox emails | public web URL |
| `SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/`SMTP_PASSWORD`/`SMTP_FROM`/`SMTP_USE_TLS`/`SMTP_TIMEOUT_SECONDS` | mail transport | unused while delivery is disabled |
| `EMAIL_DELIVERY_ENABLED` | master email switch | MUST stay `false`; when `false` the dispatcher records `suppressed` intents and never opens SMTP |
| `LOG_LEVEL` | logging | `INFO` |

Secrets (`DATABASE_URL`, `OIDC_*` where applicable, `SMTP_PASSWORD`) are set in
Coolify's secret env storage — never committed. `.env.example` documents the
full list with safe local placeholders.

## Health

- Liveness: `GET /api/v1/health/live` — process/routing only; use for the
  container healthcheck.
- Readiness: `GET /api/v1/health/ready` — requires a reachable database with
  `alembic_version` present; use for traffic switching.
- Health output never contains connection strings, credentials, or stack
  traces.

## Release procedure

1. Build/push the image for the new revision.
2. Run migrations explicitly before switching traffic:
   `uv run alembic upgrade head` inside a one-off container/exec, then verify
   `uv run alembic check` reports no drift.
3. Start the new container; gate traffic on `/api/v1/health/ready`.
4. Rollback: redeploy the previous image. Migrations are additive-only within
   a release; if a rollback crosses a schema change, restore from the
   pre-release backup rather than downgrading ad hoc.

## Outbox dispatcher

Email intents accumulate in `email_outbox_entry`. Process them explicitly:

```bash
uv run python -m uribap_api.tools.process_outbox --limit 50
```

- With `EMAIL_DELIVERY_ENABLED=false` (current guarantee): each claimed row is
  marked `suppressed`, an `email_delivery_intent(outcome='suppressed')` row is
  recorded, and no SMTP connection is opened. Suppressed rows are never
  reclaimed — re-running is safe.
- The tool exits non-zero on failure so schedulers alert.

## Security headers

The app sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, `Permissions-Policy`, plus
`Cache-Control: no-store` and `Content-Security-Policy: default-src 'none'`
on `/api/*` responses — including error responses. `Strict-Transport-Security`
is intentionally NOT set by the app: the TLS-terminating proxy (Coolify's
Traefik/edge) owns HSTS so plain-HTTP local deployments are not pinned.

## Resources

- One Uvicorn worker; pool 5+5. Baseline dev RSS ~215MiB; keep the production
  container limit ≥512MiB until load-tested.
- No Redis/queue/worker services; the outbox dispatcher is a scheduled command.
