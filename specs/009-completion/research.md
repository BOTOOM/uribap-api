# Research: Meal Completion

## Findings

- `inventory_movement` already carries `movement_type`, `source_type`, `source_id`,
  `operation`, `idempotency_key`, `request_hash`, and `result_quantity_on_hand` —
  completion reuses the ledger without new movement columns.
- `LedgerBalance.apply` enforces unit equality, quantum rounding, and no-negative
  balances; FEFO allocation only needs a deterministic lot order.
- `forecast` scaling (`servings/base_servings`, `ROUND_HALF_UP` quantum) defines the
  planned amount per recipe ingredient — completion copies that formula so planned
  lines equal what demand projection showed.
- `meal_plan_entry` gained `uq_meal_plan_entry_household` in 008, enabling the
  tenant-safe composite FK for completions.
- Shopping's `*_operation` receipt pattern (operation + key + request hash + JSONB
  payload) covers replay for complete/correct/reopen.
- `preparation_task` shows the partial-unique-index convention for one active row
  per parent; the same pattern enforces one `recorded` completion per entry.

## Decisions

- One `recorded` completion per entry; `reopened` rows stay as history and do not
  block re-completion.
- Corrections reverse the line's movements and re-deduct — never mutate movements
  in place — so the ledger stays append-only and auditable.
- Insufficient stock aborts the whole write (409); partial deductions would be
  misleading for reconciliation.
- Consumption excludes expired and unavailable lots (`waste` reporting stays out of
  scope).
