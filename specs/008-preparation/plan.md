# Implementation Plan: Preparation Engine

## Stack layers

1. **Spec** — this artifact set.
2. **Domain** — pure task state machine, deterministic `due_at` computation (meal-type
   start times, household timezone, lead minutes), derived-task fingerprinting, manual
   task validation, with `tests/unit/domain/test_preparation_policies.py` written first.
3. **Persistence** — `preparation_models.py` (`preparation_task`,
   `preparation_operation`), migration adding both tables plus the
   `uq_meal_plan_entry_household` unique constraint required by the composite FK, and
   `tests/integration/test_preparation_schema.py`.
4. **Service** — `preparation_service.py` (derivation on approve inside the planning
   transaction, manual creation, transitions, receipt replay),
   `api/preparation_schemas.py`, `api/preparation.py`, rule management routes under
   `api/recipes.py`, integration tests, OpenAPI export.

## Key decisions

- Derivation hooks into `planning_service.transition_plan` on `APPROVE`, in the same
  session/transaction — the plan state change and its derived tasks commit atomically.
- `due_at` is computed by a pure function of `(planned_date, meal_type, lead_minutes,
  household.timezone)` so it is deterministic and unit-testable without a database.
- Derived dedup uses a partial unique index on `(household_id, fingerprint)` where
  `origin='derived'`; re-approval is an insert-missing + cancel-stale reconciliation.
- Rule management lives on the recipe-version routes and is draft-only, matching the
  existing `can_edit_version` invariant.

## Models

- Architecture: `gpt-5-6-luna-max`; implementation: `gpt-5-6-sol-high`;
  transaction/security review: `gpt-5-6-terra-high`; bounded fixes: `swe-2-high`.
