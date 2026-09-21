# Convergence: Deterministic Demand Forecasting

**Status**: implemented and verified — all tasks T001–T008 complete.

## Delivered

- `domain/forecast/policies.py`: pure deterministic projection — window validation (≤62 days, `from <= to`), `Decimal` serving scaling (`servings / base_servings`, `ROUND_HALF_UP` six places), aggregation per `(ingredient_id, unit)` with required/optional split, zero-line suppression, and `max(0, total - on_hand)` shortfall.
- `application/forecast_service.py`: read-only projection over `approved` plans overlapping the window, entries inside `[from_date, to_date]`, pinned recipe-version ingredients, and available non-expired lots at `from_date`; deterministic response ordering by ingredient name/unit/id.
- `api/forecast.py`: `GET /forecast/demand` with `from_date`/`to_date` defaults (today → +6) and Problem Details `401`/`403`/`422`; registered in the API router.
- Contract doc `contracts/forecasting.md` and regenerated `openapi/openapi.json`.

## Verification

See `quickstart.md` evidence: Ruff/format/Pyright clean; 16 pure policy tests; 4 PostgreSQL service tests covering scaled shortfall, expired-lot exclusion, draft exclusion, deterministic identical payloads, read-only (no operation receipts), window validation, and tenant isolation; OpenAPI export check; pip-audit clean; Docker build `uribap-api:006` PASS.

## Decisions carried into 007

- Demand lines keep `(ingredient_id, unit)` granularity — shopping consumes the same lines and decides on `optional_amount`.
- No stored snapshot: determinism makes recomputation authoritative; a snapshot table remains a possible additive change if audit needs it.
- Availability is evaluated at `from_date`, not per day — documented in `data-model.md` and `research.md`.

## Remaining work

None in scope. Shopping projection/list, purchases, preparation derivation, and consumption posting are phases 007–009.
