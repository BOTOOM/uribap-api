# Inventory API Contract

Base path: `/api/v1`. Every route requires a bearer token, active membership, and `X-Household-ID` (UUID). JSON timestamps are UTC ISO-8601. Decimal amounts are JSON strings matching `^(0|[1-9]\d{0,11})(\.\d{1,6})?$`; values are finite, positive for lot creation, and signed/non-zero for adjustments.

## `GET /inventory?include_expired=false`

Response `200`:

```json
{"items":[{"id":"uuid","ingredient_id":"uuid","quantity_on_hand":"2.500000","unit":"kg","location":"pantry","available":true,"expiration_date":"2026-10-01","notes":null,"updated_at":"2026-09-21T12:00:00Z"}]}
```

When `include_expired=false`, expired or unavailable lots are excluded. `401`, `403`, and `422` use Problem Details.

## `POST /inventory/lots`

Request:

```json
{"ingredient_id":"uuid","quantity":"2.500000","unit":"kg","location":"pantry","expiration_date":"2026-10-01","notes":"sealed"}
```

Response `201`: `InventoryLotResponse`. `404` ingredient not found, `403` cross-household, `409` transaction conflict, `422` invalid precision/unit.

## `POST /inventory/adjustments`

Headers: `Idempotency-Key` optional, max 128 characters. Request:

```json
{"lot_id":"uuid","delta":"-0.500000","unit":"kg","movement_type":"manual_adjustment","source_type":null,"source_id":null}
```

Response `200`: updated `InventoryLotResponse`. A repeated `(household, operation, key)` with the same request hash returns the original result; a different hash returns `409`. `409` also covers no-negative/unit/locking conflicts; `401`, `403`, `404`, and `422` are Problem Details.

## `GET /inventory/lots/{lot_id}/movements`

Response `200`: `{ "items": [InventoryMovementResponse] }`, ordered oldest-first. Movement rows are append-only and include operation, request hash metadata (never secrets), source, actor, and result balance.

## Error shape

```json
{"type":"https://uribap.app/problems/conflict","title":"Inventory balance conflict","status":409,"code":"conflict","detail":"Inventory balance cannot become negative.","request_id":"uuid"}
```
