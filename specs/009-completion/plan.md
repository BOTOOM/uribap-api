# Implementation Plan: Meal Completion and Reconciliation

## Stack layers

1. **Spec** — this artifact set.
2. **Domain** — pure policies in `domain/completion/policies.py`: completion state
   machine (`recorded → reopened`), version check, planned-consumption scaling
   (reuses `scale_factor` semantics from forecast), deterministic FEFO allocation
   over a lot list, and explicit-line validation. Unit tests first.
3. **Persistence** — `completion_models.py` (`meal_completion`,
   `meal_completion_line`, `completion_operation`), migration adding all three
   tables plus `uq_meal_completion_household` for the composite FK, and schema
   integration tests.
4. **Service** — `completion_service.py` (complete-entry transaction with FEFO
   deduction, line correction with reversal + re-deduction, reopen with full
   reversal, receipt replay), `api/completion_schemas.py`, `api/completion.py`,
   integration + route tests, OpenAPI export.

## Key decisions

- Consumption writes `meal_consumption` movements (`delta < 0`) with
  `source_type = 'meal_completion_line'`, `source_id = line_id`, and
  `result_quantity_on_hand` per lot — the same ledger fields shopping purchases use,
  so the audit trail is uniform.
- Reversal movements (`movement_type = 'reversal'`, `delta > 0`) restore the exact
  lots that were deducted; a line's net consumption is always inspectable from its
  movements.
- Completing requires the plan `approved` at write time; the plan row is not
  mutated — only read inside the completion transaction.
- Insufficient stock aborts the entire completion (`409`) rather than partial
  deduction, keeping the ledger auditable and the API honest.
- FEFO ordering is `expiration_date ASC NULLS LAST, id` over
  `available AND (expiration IS NULL OR expiration >= today)` — deterministic and
  unit-testable.

## Models

- Architecture: `gpt-5-6-luna-max`; implementation: `gpt-5-6-sol-high`;
  transaction/security review: `gpt-5-6-terra-high`; bounded fixes: `swe-2-high`.
