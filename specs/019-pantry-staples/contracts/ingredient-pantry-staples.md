# Ingredient Pantry-Staple Contract

## REST schemas

- `IngredientCreate.pantry_staple`: optional Boolean, defaults to `false`.
- `IngredientUpdate.pantry_staple`: optional nullable Boolean; omission leaves the stored value
  unchanged.
- `IngredientResponse.pantry_staple`: required Boolean in every response.
- Household create/get/update/list behavior is tenant-scoped as today. Updating a global ingredient
  continues to return HTTP 403.

## MCP

- `uribap_create_ingredient` accepts optional `pantry_staple`, default false.
- `uribap_update_ingredient` accepts optional `pantry_staple`.
- `uribap_list_ingredients` returns `pantry_staple` for each household/global result.
- Tool descriptions state in one sentence that pantry staples are not consumed by cooking and
  appear in shopping only after stock is depleted.
