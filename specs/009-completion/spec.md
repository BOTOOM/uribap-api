# Feature Specification: Meal Completion and Reconciliation

**Feature Branch**: `009-completion`  **Status**: Ready for implementation

## User Stories

- **US1 (P1)**: A household member marks an entry of an `approved` meal plan as
  cooked; the API records a `meal_completion` and deducts inventory with a
  deterministic FEFO allocation (`meal_consumption` movements) in one transaction.
- **US2 (P1)**: The member reviews each completion line — planned amount (recipe
  scaled by `servings/base_servings`) versus the actual amount consumed — and can
  record an actual amount that differs from the plan.
- **US3 (P1)**: The member corrects a completion line; the API reverses that line's
  consumption movements and deducts the corrected amount, leaving a full audit
  trail.
- **US4 (P1)**: The member reopens a completion recorded by mistake; the API
  reverses every consumption movement it created and marks the completion
  `reopened`, allowing the entry to be completed again later.
- **US5 (P2)**: Every mutation is idempotent and version-checked so retries and
  races cannot double-deduct or resurrect stock.

## Requirements

- **FR-001**: `meal_completion` MUST be tenant-isolated and bound to one
  `meal_plan_entry` via the composite `(meal_plan_entry_id, household_id)` FK; at
  most one `recorded` completion per entry (partial unique index). States:
  `recorded`, `reopened` (terminal for the row).
- **FR-002**: `POST /plans/{plan_id}/entries/{entry_id}/complete` MUST require an
  `approved` plan, and MUST create the completion, its lines, and the
  `meal_consumption` movements atomically. When `lines` is omitted, actuals default
  to the planned amounts; explicit `lines` MUST cover the recipe's non-optional
  ingredients and may include optional ones.
- **FR-003**: Consumption MUST deduct deterministically from lots
  (`available = true`, not expired at the operation date) ordered by
  `expiration_date ASC NULLS LAST, id` (FEFO); `unit` MUST equal the recipe line
  unit; insufficient stock MUST fail the whole completion with `409` and no partial
  write.
- **FR-004**: `meal_completion_line` MUST store `planned_amount`, `actual_amount`,
  `unit`, `optional`, and link movements via `source_type = 'meal_completion_line'`
  and `source_id = line_id`.
- **FR-005**: `POST /meal-completions/{id}/lines/{line_id}/correct` with
  `expected_version` + `actual_amount`/`unit` MUST write `reversal` movements for the
  line's consumption movements and new `meal_consumption` movements for the
  corrected amount (FEFO again), bump the completion `version`, and keep the full
  movement history.
- **FR-006**: `POST /meal-completions/{id}/reopen` with `expected_version` MUST write
  `reversal` movements restoring every consumption movement of every line, set
  `reopened_by`/`reopened_at`, bump `version`, and allow the entry to be completed
  again (new `recorded` row).
- **FR-007**: All mutations MUST accept `Idempotency-Key` and persist receipts in
  `completion_operation` (operation + request hash + stored payload); replay MUST
  return the stored payload; same-key different-hash MUST return `409`.
- **FR-008**: `GET /meal-completions` MUST list household completions ordered by
  `completed_at DESC, id`, with optional `entry_id`, `state`, `from`, `to` filters;
  `GET /meal-completions/{id}` MUST return one completion with its lines and
  resolved `ingredient_name`/`recipe_name`/`planned_date`/`meal_type` for display.
- **FR-009**: Errors MUST use Problem Details with `401`, `403`, `404`, `409`, and
  `422` documented in OpenAPI.
- **FR-010**: Completion MUST NOT mutate meal-plan state or shopping lists; it only
  reads the approved plan entry and recipe version, and writes
  `meal_completion*`, `inventory_movement`, and lot balances. Email and
  notifications are out of scope.

## Acceptance

- Completing an approved entry deducts each ingredient FEFO and shows planned vs
  actual; repeating the same `Idempotency-Key` returns the original payload without
  new movements.
- Completing with insufficient stock returns `409` and writes nothing.
- Correcting a line leaves reversal + new consumption movements and updates the
  displayed actual.
- Reopening restores all deducted quantities; the entry can be completed again.
- A stale `expected_version` returns `409` with no partial write; cross-household
  access returns `404`/`403`.

## Out of scope

Waste tracking UI (the `waste` movement type exists but reporting flows defer),
partial-lot selection by the user (FEFO is fixed), reopen reason moderation,
notifications, email delivery, and deployment.
