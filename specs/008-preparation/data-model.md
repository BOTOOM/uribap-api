# Data Model: Preparation

## recipe_preparation_rule (existing)

Managed through new API routes. Draft versions only. `ingredient_id` optional and
tenant-checked on write; `lead_minutes >= 0`; `instruction` required (1–2000 chars).

## preparation_task

`id`, `household_id` FK, `origin` (`derived`/`manual`), `task_type`
(`defrost`/`soak`/`marinate`/`prepare_ahead`/`manual`), `title` String(200),
`instruction` Text nullable, `due_at` timestamptz, `status`
(`pending`/`completed`/`cancelled`), `version` int >= 1, `meal_plan_entry_id`
nullable, `recipe_version_id` nullable FK, `ingredient_id` nullable FK,
`amount` NUMERIC(18,6) nullable, `unit` String(8) nullable,
`fingerprint` String(64) nullable, `created_by_user_id`, `completed_by_user_id`
nullable, `completed_at` nullable, timestamps.

Constraints:

- Composite FK `(meal_plan_entry_id, household_id)` → `meal_plan_entry(id, household_id)`
  (requires new `uq_meal_plan_entry_household`).
- Partial unique `(household_id, fingerprint)` WHERE `origin = 'derived'`.
- CHECK `status`/`origin`/`task_type` value sets, `version >= 1`, `amount IS NULL OR amount > 0`,
  `(amount IS NULL) = (unit IS NULL)` (amount/unit provided together),
  `origin = 'derived' → fingerprint IS NOT NULL AND meal_plan_entry_id IS NOT NULL`,
  `status = 'completed' → completed_by_user_id IS NOT NULL AND completed_at IS NOT NULL`.

## preparation_operation

Idempotency receipts: `id`, `household_id`, `operation`, `idempotency_key`,
`request_hash`, `result_payload` JSONB, `created_at`; unique
`(household_id, operation, idempotency_key)`.

## Invariants

- Derivation runs inside the plan-approve transaction; completed/cancelled tasks are
  never mutated by derivation.
- `due_at` derives only from `(planned_date, meal_type, lead_minutes, timezone)`.
- Version increments under the task row lock on every mutation.
- Tenant checks on every read/write via `household_id`.
