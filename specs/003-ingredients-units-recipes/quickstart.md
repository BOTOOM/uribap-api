# Quickstart: Ingredients, Units, and Recipes

```bash
uv sync --locked
uv run alembic upgrade head
uv run ruff check .
uv run pyright
uv run pytest tests/unit tests/api tests/integration
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
uv run pip-audit
```

Use only synthetic household data. Validate dimension rejection, ingredient tenant isolation, draft/publish/version immutability, search/favorite behavior, and OpenAPI/Web client synchronization. No email or deployment is required for this phase.
