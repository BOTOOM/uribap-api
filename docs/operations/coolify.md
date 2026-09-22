# Coolify Operations Runbook

This document describes how the API image is configured and operated on a
Coolify-style Docker deployment. Deployment itself is out of scope for this
phase — this runbook is the contract a future deploy must satisfy.

## Reference deployment layout

Target production layout on a personal domain (e.g. `example.com`):

| Piece | Where | Public URL | Notes |
| --- | --- | --- | --- |
| Web (Next.js) | Vercel | `https://app.example.com` | env vars per `web/docs/operations/vercel.md` |
| API (this repo) | Coolify → Git repo → Dockerfile | `https://api.example.com` | serves REST + `/api/v1/mcp` |
| PostgreSQL | Coolify → Databases → PostgreSQL | internal only | **shared**: one instance, one database per project |
| ZITADEL | Coolify → Docker Compose resource (`identity/compose.coolify.yml`) | `https://auth.example.com` | **shared**: one instance, one project+client per app |

### 1. Shared PostgreSQL (once)

1. Coolify → **New Resource → Database → PostgreSQL** (18-alpine). Pick the
   server; when asked for the Docker network destination, choose a named
   network (e.g. `shared`) — every stack that needs this DB will join it.
2. Start it, copy the generated `postgres` superuser password and the
   internal hostname (container name, e.g. `postgresql-abc123`).
3. Create the Uribap database once — Coolify UI → the Postgres resource →
   terminal/exec:
   `psql -U postgres -c "CREATE DATABASE uribap OWNER postgres"` —
   or use `psql` locally against the Public URL if you temporarily enable it.
4. For any **future project**: repeat step 3 with a new database name; never
   share one database between apps.

### 2. Shared ZITADEL (once)

1. Coolify → **New Resource → Docker Compose** → paste
   `identity/compose.coolify.yml` from this repo.
2. Set secrets in the stack's Environment Variables (see the header comment
   of the compose file for the full list): `ZITADEL_DOMAIN`,
   `ZITADEL_MASTERKEY`, `POSTGRES_HOST` (the shared Postgres container name),
   `POSTGRES_ADMIN_PASSWORD`, `ZITADEL_DB_PASSWORD`, `ZITADEL_ADMIN_*`,
   `ZITADEL_SMTP_*` (Brevo or another relay).
3. Domains per service in the Coolify UI:
   `zitadel-api` → `https://auth.example.com`,
   `zitadel-login` → `https://auth.example.com/ui/v2/login`.
   (Traefik routes the longer path to the login console; the API keeps
   `h2c` via the label already in the compose file.)
4. Enable **Connect to Predefined Network** → the `shared` network so
   ZITADEL reaches Postgres.
5. Deploy. `start-from-init` provisions the `zitadel` database/user itself
   using the admin credentials — no manual schema step needed.
6. For any **future project**: no redeploy — inside ZITADEL create a new
   Org/Project + OIDC app (or rerun the seed script with different names).

### 3. API on Coolify

1. **New Resource → Git Repository** → pick this repo → build pack
   **Dockerfile** (root `Dockerfile`; Coolify builds it directly).
2. Domain: `https://api.example.com` → port `8000` → HTTPS is issued
   automatically by Coolify's Traefik.
3. Enable **Connect to Predefined Network** → `shared` (for Postgres), or
   use the Postgres **Public URL** (only if strictly necessary).
4. Set the environment contract below (secret storage), then deploy.
5. Migrations: Coolify exec → `alembic upgrade head`; verify with
   `alembic check`. The image does not auto-migrate.
6. Health check path: `/api/v1/health/live` (already in the image's
   HEALTHCHECK too).
7. MCP endpoint for agents: `https://api.example.com/api/v1/mcp` — the UI's
   "Agentes MCP" page shows this URL automatically once the web app is
   configured.

### 4. Seed the Uribap OIDC client

Run the repo seed against the shared ZITADEL with a machine PAT (ZITADEL
console → organization → the `login-client` PAT at
`/zitadel/bootstrap/login-client.pat` inside `zitadel-api`, or create an
admin PAT in the console):

```bash
cd api/identity/scripts
OIDC_ISSUER=https://auth.example.com \
ZITADEL_ADMIN_TOKEN=<pat> \
WEB_BASE_URL=https://app.example.com \
ZITADEL_LOCAL_PROJECT_NAME="Uribap" \
ZITADEL_LOCAL_WEB_CLIENT_NAME="Uribap Web" \
SEED_OUTPUT_FILE=/tmp/oidc-prod.env \
uv run python seed-local-oidc.py   # or plain python with httpx installed
```

It creates the project + OIDC web app (redirects to `WEB_BASE_URL`,
`devMode` off outside localhost) and writes the env block for both repos.

### 5. Web on Vercel

Project from the `web/` repo. Env vars:

| Var | Value |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `https://api.example.com/api/v1` |
| `URIBAP_API_INTERNAL_URL` | `https://api.example.com/api/v1` (no internal network on Vercel) |
| `AUTH_SECRET` | ≥32 random chars |
| `AUTH_ZITADEL_ID` / `AUTH_ZITADEL_SECRET` | from the seed output |
| `AUTH_ZITADEL_ISSUER` | `https://auth.example.com` |
| `AUTH_TRUST_HOST` | `true` |

Back on the API set `CORS_ORIGINS=https://app.example.com` and
`WEB_BASE_URL=https://app.example.com` (email links).

## Build

- Coolify deploys `Dockerfile` at the repository root (multi-stage Alpine,
  non-root `app`, uv-locked `uv sync --frozen --no-dev`; runtime carries
  only `/opt/venv` — no uv, no package managers).
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
- MCP: `POST /api/v1/mcp` — streamable-HTTP endpoint for external agents;
  requires `Authorization: Bearer uribap_mcp_*` and shares this image.
- Readiness: `GET /api/v1/health/ready` — requires a reachable database with
  `alembic_version` present; use for traffic switching.
- Health output never contains connection strings, credentials, or stack
  traces.

## Release procedure

1. Build/push the image for the new revision.
2. Run migrations explicitly before switching traffic:
   `alembic upgrade head` inside a one-off container/exec, then verify
   `alembic check` reports no drift. (The image ships the venv on PATH; `uv`
   is build-time only.)
3. Start the new container; gate traffic on `/api/v1/health/ready`.
4. Rollback: redeploy the previous image. Migrations are additive-only within
   a release; if a rollback crosses a schema change, restore from the
   pre-release backup rather than downgrading ad hoc.

## Outbox dispatcher

Email intents accumulate in `email_outbox_entry`. Process them explicitly:

```bash
python -m uribap_api.tools.process_outbox --limit 50
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
