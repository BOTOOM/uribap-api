# Inventory API Contract

- `GET /api/v1/inventory?include_expired=` returns lots and balances.
- `POST /api/v1/inventory/lots` creates a lot and initial purchase movement transactionally.
- `POST /api/v1/inventory/adjustments` applies a signed Decimal delta to a lot with `Idempotency-Key`.
- `GET /api/v1/inventory/lots/{lot_id}/movements` returns append-only history.

All routes require `X-Household-ID`, bearer authentication, active membership, matching unit, and Problem Details errors.
