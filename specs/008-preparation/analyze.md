# Analyze: Preparation

## Consistency

- FR-002 composite FK requires `uq_meal_plan_entry_household`; added in the same
  migration (T004) — consistent with `uq_meal_plan_household`,
  `uq_inventory_lot_household`, and `uq_shopping_list_household`.
- FR-003 derivation timing is inside the approve transaction (not a scheduler) —
  consistent with FR-010's "no writes to meal-plan tables" because derivation only
  reads entries and writes `preparation_task`.
- FR-004 stale-fingerprint cancellation applies only to `pending` derived tasks, so
  derivation never resurrects user-resolved work — consistent with FR-005's closed
  state machine.
- Rule management is draft-only per `can_edit_version` (phase 003 invariant), while
  derivation reads rules of `published` versions — no contradiction: published
  versions are immutable, so derived tasks remain reproducible.

## Risks

- Household timezone strings may be invalid; policy falls back to UTC (FR-003).
- Two concurrent approvals could race on derived inserts; the partial unique index +
  receipt replay converges to one visible outcome.
- `due_at` in the past is allowed (e.g. late approval); the UI surfaces overdue
  tasks rather than blocking.
