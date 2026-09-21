# Converge: Meal Completion and Reconciliation

## Scope delivered

- `domain/completion/policies.py` — pure completion state machine
  (`recorded → reopened`), optimistic-version check, planned-line scaling (same
  `servings/base_servings` factor as demand forecasting), explicit actual
  overrides (covers required ingredients, drops uncovered optional lines,
  rejects duplicates/unknowns/zero), and deterministic FEFO allocation over lots
  (`expiration_date ASC NULLS LAST, id`; expired lots excluded).
- `domain/inventory/ledger.py` fix — `validate_delta` no longer rejects negative
  deltas (it validated `normalized < 0` via `quantize_amount`), so
  `meal_consumption`/`waste`/`reversal` movements can finally decrement balances;
  absolute range and non-zero rules are preserved.
- `infrastructure/persistence/completion_models.py` + migration `b6e3d9f2a815` —
  `meal_completion` (composite FK to `meal_plan_entry`, partial unique index for
  one `recorded` row per entry, state/version/reopened-field CHECKs,
  `uq_meal_completion_household`), `meal_completion_line` (composite FK,
  `(completion, ingredient, unit)` unique, amount/unit/position CHECKs), and
  `completion_operation` (idempotency receipts).
- `application/completion_service.py` — `complete_entry` locks the plan
  (must be `approved`), derives planned lines or validates explicit ones, and
  writes `meal_consumption` movements with `source_type='meal_completion_line'`
  in the same transaction; insufficient stock aborts everything. `correct_line`
  reverses the line's net consumption per lot and re-deducts the corrected
  amount FEFO. `reopen_completion` reverses every line and frees the entry for
  re-completion. All mutations persist receipts and replay stored payloads.
- `api/completion.py` + `api/completion_schemas.py` —
  `POST /plans/{id}/entries/{id}/complete` (201), `GET /meal-completions`
  (`entry_id`/`state`/`from`/`to` filters), `GET /meal-completions/{id}`,
  `POST .../lines/{id}/correct`, `POST .../reopen`; Problem Details
  401/403/404/409/422; routers registered; OpenAPI regenerated (54 paths).

## Verification

All gates in `quickstart.md` pass, including the full suite (`170 passed,
2 skipped`) against a clean PostgreSQL `uribap_ci` at head `b6e3d9f2a815` with
zero `alembic check` drift; `pip-audit` clean; Docker image boots and serves
`/api/v1/health/live`.

## Design notes

- Completion is the first feature that mutates inventory balances; every delta
  lands in `inventory_movement` with `result_quantity_on_hand`, so a line's net
  consumption is inspectable from its movements alone (reversal restores exactly
  what was deducted, per lot).
- Corrections never rewrite movement history: reversal + fresh FEFO deduction
  keeps the ledger append-only and auditable.
- `recorded` uniqueness is enforced by a partial index, so reopening frees the
  entry without deleting history; re-completion creates a new row.
- The plan is read (locked) but never mutated — FR-010 holds by construction.

## Remaining work

None for API phase 009. Web phase 009 consumes the `v9` contract.
