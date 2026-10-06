# Ingredient Listing Contract

## REST

`GET /api/v1/ingredients` accepts the existing filters plus an optional opaque continuation cursor:

| Parameter | Type | Default | Behavior |
|---|---|---:|---|
| `query` | string or null | `null` | Existing normalized-name substring filter |
| `dimension` | string or null | `null` | Existing `count`, `mass`, or `volume` filter |
| `include_global` | boolean | `true` | Include the global catalog when true |
| `limit` | integer 1–100 | `50` | Maximum number of returned items |
| `cursor` | string or null | `null` | Continue after the last item from a prior page |

The listing remains scoped to the active household and non-archived ingredients. To continue a
filtered listing, a client repeats its original filters along with the returned cursor.

The order is ascending by `(normalized_name, id)`. The URL-safe Base64 cursor represents JSON with
`n` (the normalized name) and `id` (the UUID string). Consumers must treat it as opaque.

Response shape:

```json
{
  "items": ["<IngredientResponse>", "..."],
  "page_info": {
    "next_cursor": "<opaque cursor or null>",
    "limit": 2
  }
}
```

The response contains no more than `limit` items. `next_cursor` is non-null only when another
matching item exists, and is `null` on the final page.

Each request evaluates the current catalog; the cursor does not preserve a snapshot across
concurrent catalog edits.

An invalid cursor returns HTTP `422` with the existing `application/problem+json` Problem Details
shape and `code: "validation_error"`.

## MCP

`uribap_list_ingredients` accepts an optional `cursor` argument. Existing `query`, `dimension`,
`include_global`, and `limit` arguments continue to filter the page. Its result keeps the current
`items` and page-local `count` fields and adds:

```json
{
  "count": 2,
  "items": ["<IngredientResponse>", "..."],
  "next_cursor": "<opaque cursor or null>"
}
```

## Compatibility

- Existing callers that omit `cursor` continue to receive the first page with the existing default
  limit and filters.
- No ingredient fields, writes, authorization rules, or persistence behavior change.
- The REST page-info schema is typed with the existing shared `PageInfo` model.
