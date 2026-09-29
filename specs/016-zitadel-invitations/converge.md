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
