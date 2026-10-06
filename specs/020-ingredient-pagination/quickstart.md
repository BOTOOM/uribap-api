# Ingredient Pagination Quickstart

## Prerequisites

Use the repository UV environment and PostgreSQL integration database. If the local API database
is not initialized, follow the API environment blueprint:

```bash
cp -n .env.example .env
docker compose up -d db
uv run alembic upgrade head
```

Pagination adds no database migration; the upgrade command only ensures the existing test database
is ready.

## Validate REST, MCP, and OpenAPI behavior

```bash
uv run pytest \
  tests/integration/test_ingredient_routes.py \
  tests/integration/test_mcp_ingredients.py \
  tests/integration/test_mcp_transport.py \
  tests/api/test_openapi.py -q
```

The focused tests must verify two-page traversal at `limit=2`, same-name tie ordering without gaps
or duplicates, a null final cursor, filter-preserving pagination, invalid-cursor `422` Problem
Details, and MCP continuation with existing response fields.

Regenerate and validate the canonical OpenAPI document:

```bash
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi
PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check
```

## Validate code quality

```bash
uv run ruff check \
  src/uribap_api/application/ingredient_service.py \
  src/uribap_api/api/ingredients.py \
  src/uribap_api/api/recipe_schemas.py \
  src/uribap_api/mcp/tools_catalog.py \
  tests/integration/test_ingredient_routes.py \
  tests/integration/test_mcp_ingredients.py \
  tests/api/test_openapi.py
uv run ruff format --check \
  src/uribap_api/application/ingredient_service.py \
  src/uribap_api/api/ingredients.py \
  src/uribap_api/api/recipe_schemas.py \
  src/uribap_api/mcp/tools_catalog.py \
  tests/integration/test_ingredient_routes.py \
  tests/integration/test_mcp_ingredients.py \
  tests/api/test_openapi.py
uv run pyright
```
