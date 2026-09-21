# Data Model: Meal Planning

## meal_plan

`id`, `household_id`, `week_start_date` (Monday), `state`, `version` integer starting at 1, `created_by_user_id`, timestamps. Unique `(household_id, week_start_date)` where `state <> 'archived'` is enforced by a partial unique index on non-archived plans. Version increments on every entry mutation and transition.

## meal_plan_entry

`id`, `household_id`, `meal_plan_id`, `planned_date`, `meal_type`, `recipe_version_id`, `servings`, `position`, `notes`, `added_by_user_id`, timestamps. Composite FK `(meal_plan_id, household_id)` → `meal_plan(id, household_id)`; FK `recipe_version_id` → `recipe_version.id`. Check `servings > 0`. `planned_date` MUST fall inside the plan week (checked in service; seven-day range).

## meal_plan_state_event

`id`, `household_id`, `meal_plan_id`, `from_state`, `to_state`, `actor_user_id`, `note`, `created_at`. Append-only: PostgreSQL MUST reject `UPDATE`/`DELETE`. Composite FK `(meal_plan_id, household_id)`.

## meal_plan_operation

`id`, `household_id`, `operation`, `idempotency_key`, `request_hash`, `result_payload` JSONB, `created_at`. Unique `(household_id, operation, idempotency_key)` when the key is present. Replays MUST return `result_payload` verbatim; a same-key different-hash request MUST return `409`.

## Invariants

- Entry, event, and operation household IDs MUST equal the plan's household.
- `version` MUST only increment inside the plan-row lock; two concurrent mutations MUST NOT share a version.
- Entries are mutable only while `state = 'draft'`; transitions follow the state machine `draft → proposed → approved` with `proposed → draft` reopen and any non-archived → `archived`.
- Recipe versions referenced by entries MUST be `published` at write time and are never cascaded away.
- No plan write may touch `inventory_lot` or `inventory_movement`.
