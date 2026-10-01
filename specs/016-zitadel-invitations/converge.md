# Convergence — 016 ZITADEL household invitations

## Scope

Connect household invitation delivery to ZITADEL, add verified-email pending
invitation discovery and by-ID acceptance, preserve token acceptance, and document
deployment configuration. No database migration is expected.

## Verification record

- `uv run ruff check .` — passed.
- `uv run pyright` — 0 errors, 0 warnings, 0 informations.
- `uv run pytest -q tests/unit tests/api tests/integration/test_invitation_flows.py tests/integration/test_invitation_concurrency.py` — 235 passed; two dependency deprecation warnings.
- `uv run alembic check` — no new upgrade operations detected.
- `PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi` — regenerated the contract.
- `PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check` — passed.
- `git diff --check` — passed.
- PostgreSQL-only integration testing reused the existing local Compose database container and volume. No ZITADEL, Mailpit, or full Compose services were started.

## External-service validation

Do not start ZITADEL, Mailpit, or full Compose. ZITADEL requests are covered with
`httpx.MockTransport`; only the existing PostgreSQL integration setup may be used.

## Review follow-up

- ZITADEL user lookup now combines the exact-email filter with the configured
  organization filter.
- Invitation outbox rows start suppressed so only the synchronous route can deliver
  them; failed pending invitations can be retried with a rotated token and updated role
  and expiry.
- The ZITADEL user ID is committed to outbox template data before invite-code delivery,
  allowing a retry to resend the code without creating another account.

## Review verification

- `uv run ruff check src tests` — passed.
- `uv run ruff format --check` on all seven changed source/test files — passed. The
  repository-wide `uv run ruff format --check src tests` still reports 19 unchanged
  baseline files.
- `uv run pyright` — 0 errors, warnings, or informations.
- Focused ZITADEL, invitation-flow, outbox, API-route, and migration tests — 36 passed;
  two dependency deprecation warnings.
- Alembic upgrade/downgrade/upgrade round trip — passed; `f2b8d4e6a917` is the single
  head.
- OpenAPI exporter `--check` — passed; no schema change required regeneration.
- The existing `uribap` database was already at API 018 revision `6b1354a22e91`, which
  is not present in this independent PR 150 branch's migration graph. Tests and the
  migration round trip used a separate `uribap_review` database on the same Compose
  PostgreSQL service to preserve the existing database.
