# Quickstart: Shopping

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

Seed an approved plan with a shortfall, `POST /shopping-lists` for the window, purchase one item (verify the lot + `purchase` movement + item status change atomically), skip another, then complete the list. Replays and duplicate-window generation MUST return the stored result or `409`.

## Evidence

Pending — recorded during convergence.
