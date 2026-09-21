# Quickstart: Demand Forecasting

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

Seed an approved plan with entries, add inventory lots (one expired before the window), and call `GET /forecast/demand?from_date=…&to_date=…` twice; payloads MUST be identical, expired stock MUST NOT count, and no table row changes.

## Evidence

Pending — recorded during convergence.
