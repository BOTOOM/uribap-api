# Shopping API Contract

Base path: `/api/v1`. Every route requires a bearer token, active membership, and `X-Household-ID` (UUID). Mutations accept `Idempotency-Key` (max 128) and require `expected_version` where noted.

## `POST /shopping-lists`

Request: `{"from_date":"2026-09-28","to_date":"2026-10-04"}` (same window rules as `/forecast/demand`: `from <= to`, ≤62 days).

Response `201`: `ShoppingListResponse` `{id, from_date, to_date, state:"open", version:1, items:[ShoppingItemResponse], created_at, updated_at}` — one `pending` item per projected shortfall line, deterministic order. `409` when a non-archived list already exists for the window; `422` invalid window.

## `GET /shopping-lists/current` and `GET /shopping-lists/{list_id}`

`current` returns the newest non-archived list (`404` if none). Response `200`: `ShoppingListResponse` with `items` ordered by `position`. `404` unknown list; `403` cross-household.

## `POST /shopping-lists/{list_id}/items/{item_id}/purchase`

Headers: `Idempotency-Key` optional. Request:

```json
{"expected_version":2,"quantity":"1.000000","unit":"kg","location":"pantry","expiration_date":null,"notes":null}
```

`unit` MUST equal the item's unit (`422`); `location` is an `InventoryLocation` value (`422` otherwise); `quantity > 0`. Response `200`: `ShoppingListResponse` — the item becomes `purchased` with `purchased_amount`, `purchased_lot_id`, `purchased_at`; the lot and a `purchase` `inventory_movement` (`source_type = "shopping_item"`) are committed in the same transaction. `409` non-open list, non-pending item, version mismatch, or idempotency hash mismatch; replay returns the stored payload.

## `POST /shopping-lists/{list_id}/items/{item_id}/skip` and `/restore`

Request: `{"expected_version":N}`. `skip`: `pending → skipped`; `restore`: `skipped → pending`. Response `200`: `ShoppingListResponse`. `409` illegal transition or version mismatch.

## `POST /shopping-lists/{list_id}/complete`, `/reopen`, `/archive`

Request: `{"expected_version":N}`. `complete`: `open → completed`, requires zero `pending` items (`409` otherwise). `reopen`: `completed → open`. `archive`: `open|completed → archived` (terminal). Each bumps `version`.

## Error shape

```json
{"type":"https://uribap.app/problems/conflict","title":"List version conflict","status":409,"code":"conflict","detail":"The list changed since you loaded it.","request_id":"uuid"}
```
