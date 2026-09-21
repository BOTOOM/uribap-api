# Converge: Preparation Engine

## Scope delivered

- `domain/preparation/policies.py` — pure task state machine
  (`pending → completed|cancelled`), optimistic-version check, deterministic
  `due_at = meal_start(planned_date, meal_type, household.timezone) - lead_minutes`
  (fixed meal start times, ZoneInfo with UTC fallback), derived-task fingerprinting,
  and manual-task validation (title, `Decimal` amount/unit pair).
- `infrastructure/persistence/preparation_models.py` + migration `a8e4b2c1d603` —
  `preparation_task` (composite FK `(meal_plan_entry_id, household_id)` via the new
  `uq_meal_plan_entry_household`, partial unique index on
  `(household_id, fingerprint)` for `origin = 'derived'`, status/origin/type and
  completion-field CHECKs, `version >= 1`) and `preparation_operation` (idempotency
  receipts).
- `application/preparation_service.py` — `reconcile_derived_tasks` runs inside the
  `transition_plan` APPROVE transaction: inserts missing derived tasks (one per
  plan entry × published-version rule) and cancels `pending` derived tasks whose
  fingerprint is no longer produced; completed/cancelled tasks are never mutated.
  Manual creation, `expected_version` transitions under a row lock, and replay
  semantics identical to planning/shopping (stored `result_payload`,
  different-hash → `409`).
- `api/preparation.py` + `api/preparation_schemas.py` — `GET` (status/from/to
  filters), `POST` manual, `complete`/`cancel` with Problem Details
  401/403/404/409/422; rule management `POST|DELETE
  /recipes/{id}/versions/{vid}/preparation-rules` (draft versions only, ingredient
  tenant-checked); router registered; OpenAPI regenerated.

## Verification

All gates in `quickstart.md` pass, including the full suite (`136 passed, 3 skipped`)
against a clean PostgreSQL `uribap_ci` at head `a8e4b2c1d603` with zero
`alembic check` drift.

## Design notes

- Derivation is atomic with plan approval — the state change and its derived tasks
  commit or roll back together.
- `due_at` is a pure function of `(planned_date, meal_type, lead_minutes, timezone)`;
  no domain logic depends on wall-clock time.
- Preparation never writes to inventory, shopping, or meal-plan tables; it only
  reads plans, entries, recipe versions, rules, and ingredients.
- Rule authoring lives on recipe-version routes (draft-only), matching the existing
  `can_edit_version` invariant; the Web rule-editing surface is deferred per Web
  spec FR-007.

## Remaining work

None for API phase 008. Web phase 008 consumes the `v8` contract.
