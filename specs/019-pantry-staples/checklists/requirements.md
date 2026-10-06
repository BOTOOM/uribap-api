# Requirements Checklist: Pantry Staple Ingredients

## Product behavior

- [x] Pantry status is stored per ingredient, not per recipe line.
- [x] Existing and newly created ingredients default to non-staple.
- [x] Global ingredients remain read-only.
- [x] Staples remain visible in recipes and included in forecast demand.
- [x] Cooking does not persist, deduct, or allocate pantry-staple ingredients.
- [x] All-staple recipe completion succeeds with zero lines.
- [x] An actually empty recipe preserves its existing validation error.
- [x] Explicit staple completion lines return the exact specified 422 detail.
- [x] Forecast staples shortfall only when on-hand is zero; non-staples are unchanged.
- [x] Plan detail staples shortfall on zero stock and do not consume shared stock.
- [x] Shopping-list creation remains unchanged.
- [x] Skip, correction, and reopen behavior remains unchanged.

## Engineering constraints

- [x] Use `Decimal` and keep quantity rules in domain policies.
- [x] Add a reversible migration based on the verified current Alembic head.
- [x] Write domain and integration regressions before product implementation.
- [x] Extend REST and MCP schemas/tool behavior.
- [x] Regenerate, do not hand-edit, canonical OpenAPI.
- [x] Verify Ruff, formatting, Pyright, touched tests, migration behavior, and OpenAPI.
