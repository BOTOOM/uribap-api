# Quickstart: Identity and Households

This guide validates the feature locally with synthetic identities only. It never uses Brevo, a production issuer, real email addresses, or production credentials.

## Prerequisites

- Docker Engine and Compose plugin.
- `uv` and Python 3.14 for API checks.
- `curl` or HTTP client.
- A clean local identity project name: `uribap-identity`.

## 1. Prepare local identity variables

```bash
cd identity
cp .env.identity.example .env.identity
# Generate ZITADEL_MASTERKEY and disposable database/admin values locally.
# Never commit .env.identity.
```

The example contains placeholders only. The first-instance password/masterkey are consumed only when the dedicated ZITADEL volume is initialized.

## 2. Start the identity stack

```bash
docker compose -p uribap-identity --env-file .env.identity -f compose.identity.yml up -d --wait
```

Expected services:

- ZITADEL at `http://localhost:8080`.
- Mailpit UI/API at `http://localhost:8025`.
- Mailpit SMTP at `mailpit:1025` inside identity Compose and `localhost:1025` for local capture.
- Dedicated ZITADEL PostgreSQL not shared with the Uribap application database.

## 3. Seed a disposable OIDC application

```bash
uv run python identity/scripts/seed-local-oidc.py
```

The script prints only non-secret client identifiers and writes local ignored output. It must not print client secrets, tokens, or passwords. The bootstrap login PAT is intentionally insufficient for project/app management; use a disposable Admin API token with project/app permissions. In the observed local run, the Web PKCE application was created through the local ZITADEL Console and its client ID was written only to ignored Web env.

## 4. Start Uribap API

```bash
cp .env.example .env
# Set only local OIDC issuer/audience/JWKS/scopes and the local Mailpit SMTP host.
docker compose up -d --build
```

Validate health and discovery:

```bash
curl -fsS http://localhost:8010/api/v1/health/live
curl -fsS http://localhost:8010/api/v1/health/ready
# Identity diagnostic is separate from the foundation liveness/readiness endpoints:
curl -fsS http://localhost:8010/api/v1/health/identity
curl -fsS http://localhost:8080/.well-known/openid-configuration
curl -fsS http://localhost:8080/oauth/v2/keys
```

## 5. Run API tests

```bash
uv run ruff check .
uv run pyright
uv run pytest tests/unit -m unit
uv run pytest tests/api -m api
uv run alembic upgrade head
uv run pytest tests/integration -m integration
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
uv run pip-audit
```

The local identity integration suite is marked separately and must report `NOT RUN` rather than passing when ZITADEL/Mailpit is unavailable.

## 6. Verify required flows

- Valid access token reaches `GET /api/v1/me`.
- Wrong issuer/audience/signature/expiry/scope returns safe `401`/`403`.
- Repeated identity provisioning does not create duplicates.
- Household creation creates one owner membership.
- Second household is inaccessible to the first user.
- Member/admin/owner mutations enforce roles and last-owner invariant.
- Invitation email appears in Mailpit and no external SMTP connection is made.
- Invitation acceptance consumes exactly once and matches verified email.
- Audit events contain request ID/action/actor/household but no raw tokens.

## Observed validation on 2026-09-10

- Official-derived local stack: PostgreSQL 17.10, ZITADEL 4.16.0, Login healthy, Traefik healthy, Mailpit 1.24.2 healthy.
- ZITADEL discovery: issuer `http://localhost:8080`; JWKS returned 2 signing keys.
- API Docker: `/health/live` 200, `/health/ready` 200, `/health/identity` 200 after the Docker Host header fix.
- API static/integration gate: Ruff pass, Pyright 0 errors, 29 tests passed, 1 explicit local benchmark skip.
- Mailpit SMTP: synthetic message accepted and invitation test found the synthetic recipient/subject; no external SMTP used.
- Full PKCE/BFF/onboarding flow is verified from the Web E2E; API audience is the local project ID and local ZITADEL access tokens are JWTs.

## 7. Stop safely

```bash
docker compose -p uribap-identity -f compose.identity.yml logs > identity-test.log
docker compose -p uribap-identity -f compose.identity.yml down
```

This preserves volumes. Removing volumes is a separate, explicitly approved reset operation and is never automated by the test skill.
