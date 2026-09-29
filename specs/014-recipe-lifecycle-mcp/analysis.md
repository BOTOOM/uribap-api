# Analysis — 014 Review Follow-up

## Coverage

- R001 → commit-aware service methods and MCP-level transaction tests for create, update, and purchase.
- R002 → Pydantic amount bounds matching the persisted `NUMERIC(18,6)` columns, MCP validation before writes, and OpenAPI checks.
- R003 → exact normalized household/global ingredient lookup plus a regression with more than 100 substring matches.
- R004 → deterministic exact recipe-name selection and ambiguity errors listing candidate IDs.
- R005 → one archived-recipe edit guard shared by all requested version and metadata writes.
- R006 → `FOR UPDATE` recipe locks before publish and ingredient replacement; no schema uniqueness change.
- R007 → PostgreSQL integration coverage for a held session-level migration lock.
- R008 → paired checklist, analysis, and convergence artifacts for specs 014 and 015.

## Consistency and verified schema facts

- `recipe_version_ingredient.amount` and `inventory_lot.quantity_on_hand` are `NUMERIC(18,6)`.
- Ingredient unique indexes are partial: household names are unique only where `archived_at IS NULL`; global names are unique only where both `household_id IS NULL` and `archived_at IS NULL`. Archived household names therefore do not prevent re-creation; the implementation should follow these actual index semantics rather than report a false conflict.
- `McpRuntime.call()` closes its session in `finally`; uncommitted writes are rolled back when a tool fails.
- Ingredient and recipe service methods currently commit internally, so MCP needs explicit `commit=False` paths to keep related rows in one outer transaction.
- Multiple published versions may exist in deployed data. Serialization must use the recipe row lock; adding a partial unique index is out of scope and unsafe for this review fix.

## Risks and mitigations

- A nested ingredient flush must map uniqueness `IntegrityError` to the existing 409 DomainError without poisoning the caller's transaction.
- Schema validation must occur before auto-created ingredients or recipe versions are added; MCP errors must remain actionable and must not log database credentials.
- The lock test must use a separate live PostgreSQL connection and always release the held lock, including on assertion failure.
- Default `commit=True` preserves existing REST/service callers; add regression coverage for unchanged REST behavior through the existing suite.

## Open questions

None. The existing partial-index predicates and column precision were inspected; the settled design fits the current schema without a migration.
