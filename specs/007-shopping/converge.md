# Converge: Shopping Projection and Purchases

## Scope delivered

- `domain/shopping/policies.py` — pure state machines for lists
  (`open → completed`, `completed → open`, `open|completed → archived`) and items
  (`pending → purchased|skipped`, `skipped → pending`), optimistic-version check, and
  `Decimal` purchase validation via the shared ledger quantization.
- `infrastructure/persistence/shopping_models.py` + migration `c7d4e2f8a915` —
  `shopping_list` (partial unique index per household/window on non-archived lists),
  `shopping_item` (composite FK to the list, status/purchase CHECKs, unique line per
  ingredient+unit), and `shopping_operation` (idempotency receipts).
- `application/shopping_service.py` — creates lists from the phase 006 deterministic
  projection (`needed_amount = shortfall_amount`, `optional_amount` copied, one item
  per shortfall line, empty list allowed), list/item mutations under a row lock with
  `expected_version`, atomic purchase writing lot + `purchase` movement
  (`source_type = "shopping_item"`, `source_id = item_id`) + item status in one
  transaction, and replay semantics identical to planning (stored `result_payload`,
  different-hash → `409`).
- `api/shopping.py` + `api/shopping_schemas.py` — 9 routes with Problem Details
  401/403/404/409/422; router registered; OpenAPI regenerated.

## Verification

All gates in `quickstart.md` pass, including the full suite (`113 passed, 2 skipped`)
against a clean PostgreSQL database at head `c7d4e2f8a915` with zero `alembic check`
drift. Docker image builds and serves `/api/v1/health/live`.

## Design notes

- The list generation reuses `forecast_service.demand_forecast` so projection logic
  stays single-sourced; shopping never touches `meal_plan*` tables (read-only via the
  forecast service) and never mutates inventory outside the purchase transaction.
- Purchase `unit` must equal the item unit (422 otherwise); unit conversion is out of
  scope per spec.
- `complete` requires zero pending items (409); `archived` is terminal.
- The dev database retains the documented pre-hardening inventory shape; the clean
  `uribap_ci` database is the canonical local target, matching CI.

## Remaining work

None for API phase 007. Web phase 007 consumes the `v7` contract.
