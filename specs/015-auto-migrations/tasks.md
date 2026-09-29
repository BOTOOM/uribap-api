# Tasks — 015

- [x] Unit tests first: retries, timeout exit, advisory lock, unlock on upgrade error
- [x] Integration test: repeated migration run is idempotent and leaves Alembic at head
- [x] `uribap_api.tools.migrate`: bounded DB wait, advisory lock, Alembic upgrade, cleanup
- [x] Dockerfile and Compose run migrations before Uvicorn, with opt-out and health start period
- [x] `.env.example` and Coolify/foundation docs describe automatic migration and rolling safety
- [x] Build and run image against fresh DB; verify upgrade, no-op restart, readiness, and failure exit
- [x] Ruff, pyright, tests, and `alembic check` pass
