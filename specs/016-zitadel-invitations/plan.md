# Plan — 016 ZITADEL household invitations

## Models

- Primary `gpt-5-6-luna-max` (domain architecture), implementation `gpt-5-6-sol-high`,
  security and transaction reviewer `gpt-5-6-terra-high`, long-context analysis
  `glm-5-3-max`, bounded fixes `swe-2-high`.
- Model IDs follow the API `AGENTS.md` matrix; `devin models list` is unavailable in
  this environment.

## Design

No database migration or dependency is required. Add ZITADEL API URL, service-token,
organization, invite-template, and application-name settings. Resolve the API URL to
the configured value or OIDC issuer, remove trailing slashes, reject half-configured
credentials, and require HTTPS in production. Derive the Login V2 invite URL when no
custom template is provided. Never include email, credential, or response-body data in
directory exceptions or logs.

Add a synchronous `httpx` user-directory client using the existing OIDC timeout. It
will query an exact, case-insensitive email; create a human user with `returnCode: {}`;
derive and truncate required profile names; and request a ZITADEL invite code. Keep the
directory behind a FastAPI-overridable dependency. After the existing invitation
creation transaction commits, branch to ZITADEL delivery, existing-account suppression,
sanitized failure, or the current SMTP fallback. Delivery status is returned in the
202 response and outbox states reflect the actual outcome.

Add verified-email pending-list and by-ID acceptance routes. Filter by normalized
email, pending status, and expiry; conceal invitations for another email; lock the
invitation row for acceptance. Refactor token acceptance so token and ID routes share
the same logic after acquiring the invitation lock, preserving current membership,
audit, and event behavior.

## Files and verification

- Settings: `src/uribap_api/config.py`, `.env.example`
- Identity directory: `src/uribap_api/infrastructure/identity/zitadel_users.py`
- API dependency: `src/uribap_api/api/dependencies.py`
- Invitation schemas and routes: `src/uribap_api/api/schemas.py`,
  `src/uribap_api/api/invitations.py`
- Invitation service and outbox: `src/uribap_api/application/invitation_service.py`,
  `src/uribap_api/infrastructure/email/outbox.py`
- Operations: `docs/operations/coolify.md`
- Tests: `tests/unit/test_config.py`, new ZITADEL directory unit tests,
  `tests/api/test_invitation_routes.py`, and invitation delivery/acceptance
  integration coverage using the local PostgreSQL fixture.
- Contract: regenerate `openapi/openapi.json` with
  `PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi`.
- Verification: `uv run ruff check .`, `uv run pyright`,
  `uv run pytest -q tests/unit tests/api` plus the changed invitation integration
  files and `tests/integration/test_invitation_concurrency.py`,
  `uv run alembic check`, OpenAPI exporter `--check`, and `git diff --check`.

## Constitution check

- Tenant isolation: pending invitations are selected only by the current verified
  user's normalized email; acceptance rechecks that email under the invitation row
  lock.
- Secret handling: the service token is configuration-only and cannot appear in
  exception text or logs. Error logs contain only status code and request ID.
- Critical-flow coverage: unit, API, and PostgreSQL integration tests cover directory
  requests, delivery outcomes, email scoping, expiry, locking, and acceptance.
- Schema safety: invitation and outbox records already represent the required data;
  no migration is planned.
- Runtime scope: tests use `httpx.MockTransport`; do not start ZITADEL, Mailpit, or
  full Compose. Reuse PostgreSQL only for integration coverage.

## Escalation

Stop and ask the lead if the supplied ZITADEL v4.16 request contract differs from
the reachable API behavior, if invitation/outbox persistence cannot support the
flow without a schema change, or if the verified-email/privacy guarantees cannot
be preserved. Do not introduce a migration or weaken the security boundary to
work around such a conflict.

## Quickstart

1. Configure the API URL (or OIDC issuer), ZITADEL service token, and organization ID
   together. Leave both credential fields empty to keep application SMTP invitations.
2. In deployment, use a service account authorized as Org User Manager and a PAT; see
   [Coolify operations](../../docs/operations/coolify.md).
3. Validate directory behavior with the MockTransport unit tests and route behavior
   with the local PostgreSQL integration tests. No ZITADEL or Mailpit process is
   needed for these checks.
4. Run the verification commands listed above and confirm the OpenAPI exporter is
   synchronized.
