# Quickstart: Preparation

```bash
uv sync --locked
uv run ruff check .
uv run pyright
uv run pytest tests/unit
uv run pytest tests/api
docker compose up -d db
uv run alembic upgrade head
uv run pytest tests/integration
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
uv run pip-audit
```

Seed a recipe version with a `defrost` rule, approve a plan containing it, then
`GET /preparation-tasks` — one pending task appears with `due_at = meal start − lead`.
Complete it, verify `409` on a stale `expected_version`, re-approve after removing the
entry and see the task cancelled. Create a manual task and replay with the same
`Idempotency-Key`.

## Evidence

Pending — recorded during convergence.
