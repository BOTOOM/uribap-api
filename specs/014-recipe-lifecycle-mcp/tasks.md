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
