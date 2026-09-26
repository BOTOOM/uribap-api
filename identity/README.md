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

The helper verifies discovery/JWKS/Mailpit and prints setup guidance. It must never print a client secret, access token, refresh token, password, or masterkey. Creating an OIDC application requires the disposable Console/Admin API credentials created for this local stack; those values remain outside Git. The helper does not update existing OIDC applications; manually configure a reused application for JWT access tokens and ID-token UserInfo profile assertions.

## OIDC application settings and profile claims

The API validates signed JWT access tokens for authentication and authorization. When the default ZITADEL profile fields are needed, configure the optional, same-origin UserInfo endpoint:

```text
OIDC_USERINFO_URL=http://localhost:8080/oidc/v1/userinfo
```

Production must use HTTPS. The API retrieves profile data only after access-token validation and requires the UserInfo subject to match the token subject. Configure the ZITADEL application for JWT access tokens, Basic client authentication, authorization-code flow with PKCE, refresh-token grant, and ID-token UserInfo profile assertions. The API audience is the ZITADEL project ID; the Web application uses its OIDC client ID and secret.

Stock ZITADEL 4.16 JWT access tokens do not contain a signed `scope` claim. Keep `OIDC_REQUIRED_SCOPES` empty (the API's optional default and local seed output); do not synthesize scopes from UserInfo, which supplies profile fields only. Nonempty requirements remain enforced and will reject a token without the required provider-signed scope claim unless a separately designed introspection integration is introduced.

## Use from API and Web

For host processes:

```text
OIDC_ISSUER=http://localhost:8080
OIDC_JWKS_URL=http://localhost:8080/oauth/v2/keys
OIDC_USERINFO_URL=http://localhost:8080/oidc/v1/userinfo
OIDC_USERINFO_CONNECT_HOST=
OIDC_REQUIRED_SCOPES=
AUTH_ZITADEL_ISSUER=http://localhost:8080
```

For local API containers, keep `OIDC_USERINFO_URL` on the public local issuer origin (`http://localhost:8080/oidc/v1/userinfo`) and set `OIDC_USERINFO_CONNECT_HOST=host.docker.internal`. The API connects to the Docker host through that alias while preserving `Host: localhost:8080`; Compose supplies `extra_hosts: host.docker.internal:host-gateway`. Host-process development leaves the connect host empty. Production MUST leave it empty and use a same-origin HTTPS URL. Do not change a production issuer to accommodate local Docker.

The Web callback must be registered in the synthetic local ZITADEL application:

```text
http://localhost:3000/api/auth/callback/zitadel
```

Register `http://localhost:3000/` as the post-logout redirect URI. Identity verification and recovery email text is configured at the ZITADEL organization level under Organization Settings → Message Texts; visual appearance is a separate Branding setting. These organization settings are distinct from the per-project OIDC application settings on the shared instance. The API can test basic OIDC/JWKS without SMTP. Complete verification/reset/invitation tests require Mailpit and inspect messages through its API/UI.

## Stop without deleting data

```bash
docker compose -p uribap-identity -f compose.identity.yml logs > identity-test.log
docker compose -p uribap-identity -f compose.identity.yml down
```

Do not run `down -v` automatically. A full reset deletes the dedicated ZITADEL and Mailpit data and requires explicit approval.
