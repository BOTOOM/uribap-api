# Data Model: Shopping

## shopping_list

`id`, `household_id`, `from_date`, `to_date`, `state` (`open`/`completed`/`archived`), `version` integer starting at 1, `created_by_user_id`, timestamps. Partial unique index on `(household_id, from_date, to_date)` where `state <> 'archived'` — one live list per window. Version increments on every item mutation and transition.

## shopping_item

`id`, `household_id`, `shopping_list_id`, `ingredient_id` (FK `ingredient.id`), `unit`, `needed_amount` NUMERIC(18,6), `optional_amount` NUMERIC(18,6), `status` (`pending`/`purchased`/`skipped`), `position`, `notes`, `purchased_amount` NUMERIC(18,6) nullable, `purchased_lot_id` FK `inventory_lot.id` nullable, `purchased_at` nullable, `added_by_user_id`? — not needed; `created_at`/`updated_at`. Composite FK `(shopping_list_id, household_id)` → `shopping_list(id, household_id)`. CHECK `needed_amount > 0`, `purchased_amount IS NULL OR purchased_amount > 0`, `status` values.

## shopping_operation

`id`, `household_id`, `operation`, `idempotency_key`, `request_hash`, `result_payload` JSONB, `created_at`. Unique `(household_id, operation, idempotency_key)` when the key is present. Replays MUST return `result_payload` verbatim; a same-key different-hash request MUST return `409`.

## Invariants

- Item, receipt, and purchase household IDs MUST equal the list's household.
- `purchased_lot_id` MUST reference an `inventory_lot` of the same household; the purchase writes lot + movement + item status in ONE transaction.
- `version` MUST only increment inside the list-row lock; two concurrent mutations MUST NOT share a version.
- Items are mutable only while `state = 'open'`; `complete` requires zero `pending` items.
- Shopping MUST NOT write to `meal_plan` or `meal_plan_entry`; it reads the 006 projection and writes `inventory_lot`/`inventory_movement` only through purchases.
