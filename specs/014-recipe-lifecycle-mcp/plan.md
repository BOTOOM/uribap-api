# Plan — 014 Recipe lifecycle and MCP hardening

## Models

- Primary: `gpt-5-6-sol-high` (implementation). Reviewer: `gpt-5-6-terra-high`
  (transactions/tenant isolation). Subagent: `swe-2-high` (bounded test fixes).
  Escalation: any change to completion/inventory semantics → `gpt-5-6-luna-max`.

## Design

No migration: `recipe.archived_at` and `RecipeVersionState.ARCHIVED` already exist.

`application/recipe_service.py`:

- `update_recipe(session, membership, recipe_id, payload: RecipeUpdate) -> Recipe`
- `revise_recipe(session, membership, recipe_id, payload: RecipeRevision) -> RecipeVersion`
  - lock the recipe row (`with_for_update`) to serialize concurrent revisions;
  - latest draft → edit in place; else create `N+1` cloned from latest; apply overrides;
  - lines validated with the same rules as `replace_version_ingredients` (shared helper);
  - `publish=True` → `publish_version` semantics; single commit for the whole revision.
- `publish_version`: also sets other `published` versions of the recipe to `archived`.
- `archive_recipe` / `unarchive_recipe` (idempotent: archiving an archived recipe is a no-op).
- `planning_service._assert_published_version`: reject versions whose recipe is archived (422).

Schemas (`api/recipe_schemas.py`):

- `RecipeUpdate { name?: str(1..200), description?: str | None }` (explicit `null` clears
  description; use `model_fields_set`).
- `RecipeRevision { base_servings?: int>0, prep_minutes?: int>=0,
  items?: list[RecipeVersionIngredientUpsert] | None, publish: bool = True }`.

REST (`api/recipes.py`, all with `ERROR_RESPONSES`):

- `PATCH /recipes/{recipe_id}` → `RecipeResponse`
- `POST /recipes/{recipe_id}/revisions` → `RecipeVersionDetailResponse` (201)
- `POST /recipes/{recipe_id}/archive` / `/unarchive` → `RecipeResponse`

MCP (`mcp/tools_catalog.py`, `mcp/tools_household.py`, `mcp/tools_inventory.py`, `server.py`):
as listed in the spec. Shared ingredient-line resolution helper validates every line before
any write.

## Verification

`uv run ruff check .`, `uv run pyright`, `uv run pytest` (with `docker compose up -d db` +
`uv run alembic upgrade head`), `uv run alembic check`,
`PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi --check`.
