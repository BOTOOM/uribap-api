# Uribap Local Identity Stack

This directory is the canonical local identity harness for both Uribap repositories.

```text
ZITADEL API + Login
        │
        ├── dedicated PostgreSQL volume: zitadel-postgres-data
        └── SMTP: mailpit:1025
                    └── UI/API: http://localhost:8025
```

## Security boundary

- This stack is local-only and uses synthetic users/emails.
- Brevo, production issuers, production credentials, and real SMTP are prohibited here.
- `.env.identity` is ignored and must never be committed.
- PostgreSQL is not published to the host and is not shared with the Uribap application DB.
- `ZITADEL_FIRSTINSTANCE_*` values apply only to a fresh ZITADEL bootstrap volume.

## Start

```bash
cp .env.identity.example .env.identity
# Replace GENERATE_* placeholders with disposable local values.
docker compose -p uribap-identity --env-file .env.identity -f compose.identity.yml up -d --wait
```

Endpoints:

- ZITADEL issuer: `http://localhost:8080`
- ZITADEL console: `http://localhost:8080/ui/console`
- Mailpit UI/API: `http://localhost:8025`
- Mailpit SMTP from the host: `localhost:1025`
- Mailpit SMTP from Compose services: `mailpit:1025`

Readiness checks:

```bash
docker compose -p uribap-identity -f compose.identity.yml ps
curl -fsS http://localhost:8080/debug/ready
curl -fsS http://localhost:8080/.well-known/openid-configuration
curl -fsS http://localhost:8080/oauth/v2/keys
curl -fsS http://localhost:8025/api/v1/info
```

## Seed

After the stack is ready, run the redacted seed helper from the API repository:

```bash
uv run python identity/scripts/seed-local-oidc.py
```

The helper verifies discovery/JWKS/Mailpit and prints setup guidance. It must never print a client secret, access token, refresh token, password, or masterkey. Creating an OIDC application requires the disposable Console/Admin API credentials created for this local stack; those values remain outside Git.

## Use from API and Web

For host processes:

```text
OIDC_ISSUER=http://localhost:8080
OIDC_JWKS_URL=http://localhost:8080/oauth/v2/keys
AUTH_ZITADEL_ISSUER=http://localhost:8080
```

For containers that reach services through the host, use the container-specific `host.docker.internal` URL and keep `extra_hosts` enabled. Do not change a production issuer to accommodate local Docker.

The Web callback must be registered in the synthetic local ZITADEL application:

```text
http://localhost:3000/api/auth/callback/zitadel
```

The API can test basic OIDC/JWKS without SMTP. Complete verification/reset/invitation tests require Mailpit and inspect messages through its API/UI.

## Stop without deleting data

```bash
docker compose -p uribap-identity -f compose.identity.yml logs > identity-test.log
docker compose -p uribap-identity -f compose.identity.yml down
```

Do not run `down -v` automatically. A full reset deletes the dedicated ZITADEL and Mailpit data and requires explicit approval.
