# Quickstart: Inventory Ledger

```bash
uv sync --locked
uv run alembic upgrade head
uv run ruff check .
uv run pyright
uv run pytest tests/unit tests/api tests/integration
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
uv run pip-audit
```

Verify Decimal balances, no-negative concurrent adjustments, idempotent replay, movement reconstruction, tenant isolation, and Docker health with synthetic data.
