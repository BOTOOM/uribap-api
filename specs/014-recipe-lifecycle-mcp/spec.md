# 014 — Recipe lifecycle (edit/archive) and MCP hardening

## Problem

Agents operating a household through MCP (013) hit three gaps while loading real data:

1. Recipes cannot be edited or archived. The only way to fix a typo or change an ingredient
   amount is to create a brand-new recipe, which duplicates the catalog and breaks history.
   The REST API has no rename/archive endpoint either, even though `recipe.archived_at` exists.
2. `uribap_list_members` always fails: the tool returns a JSON list but FastMCP expects a
   dict (`Input should be a valid dictionary`).
3. `uribap_create_recipe` is not atomic from the agent's view: the recipe is committed before
   ingredient lines are resolved/validated, so a bad unit or unknown `ingredient_id` leaves an
   orphan empty draft recipe. `ingredient_id` lines are not tenant-checked before creation, and
   calling it twice with the same name silently creates a duplicate recipe.

## Scope

### Recipe lifecycle (domain + REST + MCP)

- **Update metadata** in place: `name`, `description` (recipe-level, not versioned).
  `normalized_name` is recomputed. Archived recipes cannot be edited (409).
- **Revise content** (servings, prep minutes, ingredient lines) while preserving history:
  - if the latest version is a `draft`, it is edited in place;
  - otherwise a new draft `N+1` is created, cloned from the latest version (servings, prep
    minutes, ingredient lines), and the requested changes are applied on top;
  - omitted fields keep the latest version's values; `items`, when provided, replace all lines;
  - `publish=true` (default) publishes the resulting draft.
- **Publishing** version `N` moves every other `published` version of the same recipe to
  `archived`, so a recipe has at most one active published version. Existing plan entries and
  completions that reference older versions keep working (they reference `recipe_version_id`).
- **Archive / unarchive** a recipe (soft delete via `archived_at`). Archived recipes are hidden
  from default listings and published-version pickers, and cannot be newly planned (422) nor
  have an existing entry switched to one of their versions; existing entries, forecasts and
  completions are unaffected.
- REST: `PATCH /recipes/{recipe_id}`, `POST /recipes/{recipe_id}/revisions`,
  `POST /recipes/{recipe_id}/archive`, `POST /recipes/{recipe_id}/unarchive`.

### MCP

- New tools: `uribap_update_recipe` (metadata and/or content revision in one call),
  `uribap_archive_recipe`, `uribap_unarchive_recipe`.
- Fix `uribap_list_members` → `{"count", "items"}`.
- `uribap_create_recipe`: resolve + validate every line (tenant scope, archived, unit vs
  dimension) before creating the recipe; reject a duplicate active recipe name with an
  actionable error pointing to `uribap_update_recipe`.
- `uribap_register_purchase`: accept `ingredient_name` as an alternative to `ingredient_id`
  (exact normalized match; auto-created from the unit's dimension when missing, reported in the
  response). Description corrected: the unit must match the ingredient *dimension*
  (e.g. `kg` is valid for a `g` ingredient), not the base unit.
- `uribap_get_recipe`: accept `recipe_name` as an alternative to `recipe_id`; report which
  version is the active published one and which version the listed lines belong to.
- Server `INSTRUCTIONS` document the edit/archive flow.

## Out of scope

- Recipe instructions, tags and meal-type metadata.
- Recording meals that are not part of an approved plan (tracked separately).
- Web UI changes; the web repository re-pins the regenerated OpenAPI contract separately.

## Acceptance

- Domain/service tests: metadata update, revise-in-place on draft, revise-clone on published
  (lines copied, overrides applied, history intact), publish archives previous published
  version, archive/unarchive, archived recipe blocks new planning, tenant isolation, archived
  recipe edit → 409.
- MCP transport tests: `uribap_list_members` succeeds; create → update (new version) →
  archive → unarchive through `tools/call`; `create_recipe` with an invalid line leaves no
  recipe behind; duplicate name rejected; `register_purchase` by name.
- OpenAPI regenerated; `ruff`, `pyright`, `pytest`, `alembic check`, export `--check` green.
