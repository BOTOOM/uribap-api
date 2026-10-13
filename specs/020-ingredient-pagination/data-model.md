# Data Model: Ingredient Catalog Pagination

Pagination is stateless and does not change the database schema.

## Existing ingredient row

The listing uses existing fields:

- `normalized_name`: primary ascending sort key and cursor component.
- `id`: unique ascending tie-breaker and cursor component.
- `household_id` and `archived_at`: existing visibility and active-row predicates.
- `dimension`: existing optional dimension filter.

Household-owned and global rows with equal normalized names remain distinct results; ordering by
`id` gives each a unique position.

## Ingredient listing page

The application listing result contains the returned ingredient rows and an optional next cursor.
It is derived from the database for each request and is not persisted.

- `items`: up to the requested limit of rows matching all visibility and filter predicates.
- `next_cursor`: a continuation value when an extra matching row exists; otherwise `null`.
- `limit`: the effective requested page size reported by the REST `PageInfo`.
- MCP `count`: the number of items in that page, preserving current behavior.

## Cursor

The cursor is URL-safe Base64-encoded JSON with this payload shape:

```json
{"n": "<normalized_name>", "id": "<uuid>"}
```

The cursor represents the last row included in the preceding page. On receipt, the service must
decode the value, require a string `n`, parse `id` as a UUID, and reject malformed or invalid values
with a `422` `validation_error` `DomainError`. It must not perform an unscoped row lookup using the
cursor; every query remains constrained by the active household and the caller's
`include_global` option.

## Query behavior

1. Apply household/global visibility, active-row, search, and dimension predicates.
2. If present, apply the keyset predicate strictly after `(normalized_name, id)`.
3. Order ascending by `(normalized_name, id)` and fetch `limit + 1` rows.
4. Return at most `limit` rows.
5. If the extra row exists, encode the last returned row as `next_cursor`; otherwise return
   `next_cursor: null`.

No entity lifecycle, constraints, migrations, or indexes change.

Each page is evaluated against current database state. The cursor does not preserve a snapshot
across concurrent catalog edits.
