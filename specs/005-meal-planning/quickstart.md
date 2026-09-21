# Quickstart: Meal Planning

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

Create a draft plan for a Monday, add an entry with a published recipe version, propose, approve with a different member, and verify version conflicts, append-only events, and idempotent replays. Planning must never change `inventory_lot`/`inventory_movement`.
