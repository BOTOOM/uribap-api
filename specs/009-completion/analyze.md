# Analysis: Meal Completion

## Coverage

| Requirement | Covered by |
| --- | --- |
| FR-001/004 schema | T002 |
| FR-002/003 complete + FEFO | T001, T003 |
| FR-005/006 correct + reopen | T001, T004 |
| FR-007 idempotency | T002 (receipts), T003–T005 |
| FR-008 reads | T004 |
| FR-009/010 errors + boundaries | T003–T005 |

## Consistency checks

- Planned amounts reuse the forecast scale factor — the same formula the demand
  projection used, so planned vs actual is meaningful.
- Reversal movements restore exactly the lots deducted; balances can never be
  pushed negative because `LedgerBalance.apply` validates every delta.
- Partial unique `(household_id, meal_plan_entry_id)` on `recorded` permits
  re-completion after reopen without history loss.
- The completion transaction never mutates `meal_plan`/`meal_plan_entry` or
  shopping rows — FR-010 holds by construction.

## Resolved questions

- *Completion of unapproved plans?* Rejected — only `approved` plans can consume
  inventory.
- *User-chosen lots?* No — FEFO is deterministic and not user-selectable.
- *Reopen with a reason?* Optional free-text `reopen_reason`, stored and returned.
- *Correcting to a different unit?* Rejected — `unit` must equal the line unit.
