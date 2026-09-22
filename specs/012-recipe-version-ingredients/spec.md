# 012 — Recipe version ingredients (write surface)

## Problem

`RecipeVersionIngredient` rows feed demand forecasting and meal completion, but no API
endpoint wrote them: a published recipe could be planned yet produced zero projected
demand, making the plan → forecast → shopping loop unwirable end to end.

## Scope

- `GET /recipes/{recipe_id}/versions/{version_number}` — version detail with ingredient lines.
- `PUT /recipes/{recipe_id}/versions/{version_number}/ingredients` — replace all lines of a
  draft version (ingredient must be visible to the household, unit must match the
  ingredient base unit, amounts are `Decimal`, `optional` flag supported).
- Draft-only editing: published versions are immutable (409).
- Tenant isolation via `X-Household-ID`; all contract errors in OpenAPI.

## Acceptance

- Integration tests cover: line persistence, dimension/unit validation, draft-only rule,
  household scoping.
- OpenAPI regenerated and pinned in web `contracts/uribap-api.openapi.json`.
