# Data Model: Meal Completion

## meal_completion

`id`, `household_id` FK, `meal_plan_entry_id` NOT NULL, `state`
(`recorded`/`reopened`), `version` int >= 1, `completed_by_user_id`,
`completed_at`, `reopened_by_user_id` nullable, `reopened_at` nullable,
`reopen_reason` Text nullable, timestamps.

Constraints:

- Composite FK `(meal_plan_entry_id, household_id)` → `meal_plan_entry`
  (reuses `uq_meal_plan_entry_household` from 008).
- `uq_meal_completion_household` on `(id, household_id)` (needed by the line's
  composite FK).
- Partial unique `(household_id, meal_plan_entry_id)` WHERE `state = 'recorded'`.
- CHECK `state` value set, `version >= 1`,
  `state = 'reopened' → reopened_by_user_id IS NOT NULL AND reopened_at IS NOT NULL`.

## meal_completion_line

`id`, `household_id` FK, `meal_completion_id` NOT NULL, `ingredient_id` FK,
`planned_amount` NUMERIC(18,6), `actual_amount` NUMERIC(18,6), `unit` String(8),
`optional` Boolean, `position` int >= 0, timestamps.

Constraints:

- Composite FK `(meal_completion_id, household_id)` → `meal_completion`.
- Unique `(meal_completion_id, ingredient_id, unit)` per line set.
- CHECK `planned_amount >= 0`, `actual_amount > 0`, non-empty `unit`,
  `position >= 0`.

## completion_operation

Idempotency receipts: `id`, `household_id`, `operation`, `idempotency_key`,
`request_hash`, `result_payload` JSONB, `created_at`; unique
`(household_id, operation, idempotency_key)`.

## inventory_movement (existing)

Completion writes rows with `movement_type` `meal_consumption` or `reversal`,
`source_type = 'meal_completion_line'`, `source_id = line_id`,
`result_quantity_on_hand` per lot, `operation` names
(`meal_entry_complete`, `meal_completion_line_correct`, `meal_completion_reopen`).

## Invariants

- One `recorded` completion per plan entry; a `reopened` row never blocks a new
  completion.
- Every deduction writes a movement in the same transaction as the lot update;
  `LedgerBalance.apply` still enforces no-negative balances.
- Reversal restores exactly the movements the completion created — never more.
- Tenant checks on every read/write via `household_id`.
