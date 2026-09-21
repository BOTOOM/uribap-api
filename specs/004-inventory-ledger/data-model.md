# Data Model: Inventory Ledger

## inventory_lot

`id`, `household_id`, `ingredient_id`, `quantity_on_hand NUMERIC`, `unit`, `location`, `available`, `expiration_date`, `notes`, timestamps. Check balance >= 0 and unique tenant references.

## inventory_movement

`id`, `household_id`, `lot_id`, `delta NUMERIC`, `unit`, `movement_type`, `actor_user_id`, `source_type`, `source_id`, `idempotency_key`, `created_at`. Append-only; unique `(household_id, idempotency_key)` when key is present.

## Invariants

- Lot and movement household IDs match.
- Unit matches ingredient dimension.
- Balance after movement >= 0.
- Reversals are compensating movements; history is never edited.
