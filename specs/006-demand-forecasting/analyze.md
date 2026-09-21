# Spec Kit Analysis: Demand Forecasting

**Status**: PASS — the analysis gate is complete.

## Current consistency

The spec, plan, data model, contract, traceability, checklist, and tasks agree on:

- approved-plan entries inside `[from_date, to_date]` are the only demand source; draft/proposed/archived contribute nothing;
- `Decimal` serving scaling per entry, aggregated per `(ingredient_id, unit)` with no unit conversion;
- `required_amount`/`optional_amount` split, `total_amount`, on-hand from available non-expired lots at `from_date`, and `shortfall = max(0, total - on_hand)`;
- read-only deterministic projection: no new tables, no writes, no volatile response fields, echoed window and considered plan ids;
- window defaults (today → +6 days), `from <= to`, and a 62-day cap;
- Problem Details `401`/`403`/`422` in OpenAPI;
- explicit exclusion of shopping, purchases, preparation, consumption, unit conversion, email, and deployment.

T001 is complete. Implementation tasks remain intentionally open until their tests and convergence evidence are complete.
