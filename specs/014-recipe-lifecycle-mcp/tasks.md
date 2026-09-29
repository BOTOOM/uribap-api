# Tasks — 014

- [x] Integration tests first: update/revise/publish-archives-previous/archive/unarchive/planning guard/tenant isolation
- [x] `RecipeUpdate`, `RecipeRevision` schemas
- [x] `recipe_service`: `update_recipe`, `revise_recipe`, `archive_recipe`, `unarchive_recipe`; `publish_version` archives previous published versions; shared line validation helper
- [x] `planning_service._assert_published_version` rejects archived recipes
- [x] REST routes PATCH / revisions / archive / unarchive + API route tests
- [x] MCP: fix `uribap_list_members`; new `uribap_update_recipe`, `uribap_archive_recipe`, `uribap_unarchive_recipe`
- [x] MCP: `uribap_create_recipe` validates all lines before writing + duplicate-name guard
- [x] MCP: `uribap_register_purchase` accepts `ingredient_name`; description fix
- [x] MCP: `uribap_get_recipe` by name + active version info; INSTRUCTIONS updated
- [x] MCP transport tests for the new/fixed tools
- [x] OpenAPI regenerated
- [x] ruff, pyright, pytest, alembic check, export --check green

## Review follow-up

- [x] R001 Make MCP create/update/purchase writes atomic with keyword-only service `commit` options; create one final transaction commit per tool call.
- [x] R002 Bound recipe ingredient and purchase amounts to the persisted NUMERIC(18,6) range; validate MCP inputs before writes and regenerate OpenAPI.
- [x] R003 Resolve ingredients by exact normalized household/global name, preferring household rows; handle archived-name conflicts according to the partial unique indexes.
- [x] R004 Resolve recipe names deterministically, preferring the sole active match and reporting candidate IDs for ambiguous matches.
- [x] R005 Apply the shared archived-recipe edit guard to version creation, ingredient replacement, publishing, metadata updates, and revisions.
- [x] R006 Lock the recipe row before publish and ingredient replacement to serialize competing version writes; do not add a unique index on published versions.
- [x] R007 Add real-PostgreSQL coverage proving the migration advisory lock blocks a concurrent `migrate.main()` until released.
- [x] R008 Add Spec Kit checklists, analysis, and convergence records for specs 014 and 015.

## Convergence

R001–R008 are implemented and verified. The review follow-up keeps the existing partial
ingredient uniqueness predicates and does not add a published-version unique index.
