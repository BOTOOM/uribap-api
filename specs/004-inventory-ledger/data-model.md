# Data Model: Inventory Ledger

## inventory_lot

`id`, `household_id`, `ingredient_id`, `quantity_on_hand NUMERIC`, `unit`, `location`, `available`, `expiration_date`, `notes`, timestamps. Check balance >= 0 and unique tenant references.

## inventory_movement

`id`, `household_id`, `lot_id`, `delta NUMERIC`, `unit`, `movement_type`, `actor_user_id`, `source_type`, `source_id`, `operation`, `idempotency_key`, `request_hash`, `result_quantity_on_hand`, `created_at`. Append-only; unique `(household_id, operation, idempotency_key)` when key is present. `request_hash` is a canonical hash of all mutation inputs and a replay with the same key but a different hash returns `409`; `result_quantity_on_hand` reproduces the original safe response.

## Invariants

- Lot and movement household IDs match.
- Unit matches ingredient dimension.
- Balance after movement >= 0.
- Reversals are compensating movements; history is never edited.
- A composite foreign key `(lot_id, household_id)` MUST reference the lot's `(id, household_id)` pair.
- PostgreSQL MUST reject `UPDATE` and `DELETE` on `inventory_movement`; corrections use compensating rows.
- All amounts MUST be finite and quantized to six fractional places within `NUMERIC(18,6)` before persistence.
