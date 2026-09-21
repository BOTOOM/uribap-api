# Demand Forecasting API Contract

Base path: `/api/v1`. The route requires a bearer token, active membership, and `X-Household-ID` (UUID). Read-only: no `Idempotency-Key`, no `expected_version`, no writes.

## `GET /forecast/demand`

Query parameters:

- `from_date` (date, optional): first day of the projection window; defaults to the server's current date.
- `to_date` (date, optional): last day; defaults to `from_date + 6`. MUST be `>= from_date` and the span MUST NOT exceed 62 days (`422`).

Response `200`: `DemandForecastResponse`

```json
{
  "from_date": "2026-09-28",
  "to_date": "2026-10-04",
  "considered_plan_ids": ["uuid"],
  "items": [
    {
      "ingredient_id": "uuid",
      "ingredient_name": "Rice",
      "unit": "g",
      "required_amount": "700.000000",
      "optional_amount": "0.000000",
      "total_amount": "700.000000",
      "on_hand_amount": "500.000000",
      "shortfall_amount": "200.000000"
    }
  ]
}
```

- `items` is sorted deterministically by `ingredient_name`, then `unit`, then `ingredient_id`.
- Amounts are `Decimal` strings with six decimal places.
- `considered_plan_ids` lists the approved plans whose entries fed the projection, sorted.
- Identical inputs produce an identical payload; no volatile fields.

## Errors

- `401` missing/invalid bearer token; `403` not an active household member.
- `422` `from_date > to_date`, window longer than 62 days, or malformed dates.

```json
{"type":"https://uribap.app/problems/validation","title":"Validation failed","status":422,"code":"validation_failed","detail":"from_date must be on or before to_date.","request_id":"uuid"}
```
