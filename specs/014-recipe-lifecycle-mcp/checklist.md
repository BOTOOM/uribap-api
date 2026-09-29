# Checklist — 014 Review Follow-up

- [x] MCP recipe creation, recipe updates, and purchase registration commit their related writes atomically.
- [x] `commit=False` service paths flush without committing; ingredient integrity conflicts remain recoverable through a nested savepoint.
- [x] Recipe ingredient and inventory lot quantities respect their persisted `NUMERIC(18,6)` ranges.
- [x] MCP validates all affected input before writing; quantized purchase quantities that become zero are rejected.
- [x] Exact normalized ingredient lookup searches household and global scope without a 100-result substring cap and prefers household matches.
- [x] Recipe-name lookup prefers one active match and reports all candidate IDs when the remaining matches are ambiguous.
- [x] Version creation, ingredient replacement, publishing, recipe metadata update, and recipe revision reject archived recipes with the established 409 conflict.
- [x] Publishing and ingredient replacement lock the recipe row; no partial unique index is introduced for published versions.
- [x] The migration advisory-lock integration test proves real cross-connection serialization.
- [x] Canonical OpenAPI is regenerated and `export_openapi --check` passes.
- [x] Ruff, Pyright, the full test suite, and `alembic check` pass.
