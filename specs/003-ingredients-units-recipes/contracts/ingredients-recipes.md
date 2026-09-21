# Ingredients and Recipes API Contract

Base: `/api/v1`; protected by OIDC + active household membership.

## Ingredients

- `GET /ingredients?query=&dimension=&include_global=&cursor=&limit=`
- `POST /ingredients`
- `GET /ingredients/{id}`
- `PATCH /ingredients/{id}`
- `POST /ingredients/{id}/archive`

Ingredient body includes `name`, `category`, `dimension`, `base_unit`, and optional `pack_size`.
Quantities are `{ amount: string, unit: unit|g|kg|ml|l }`. Incompatible dimensions return `422`.

## Recipes

- `GET /recipes?query=&meal_type=&tag=&archived=&cursor=&limit=`
- `POST /recipes`
- `GET /recipes/{id}`
- `POST /recipes/{id}/versions`
- `GET /recipes/{id}/versions/{version}`
- `PATCH /recipes/{id}/versions/{version}` only while draft
- `POST /recipes/{id}/versions/{version}/publish`
- `POST /recipes/{id}/favorite`
- `DELETE /recipes/{id}/favorite`
- `POST /recipes/{id}/archive`

Version payload contains base servings, prep minutes, ordered ingredient lines, instructions, meal types, tags, and preparation rules.

All mutations support `x-request-id`, `Idempotency-Key` where retry-sensitive, and `If-Match`/`expected_version` where concurrent editing applies. Errors use Problem Details.
