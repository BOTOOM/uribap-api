# Spec Kit Analysis: Shopping

**Status**: PASS — the analysis gate is complete.

## Current consistency

The spec, plan, data model, contract, traceability, checklist, and tasks agree on:

- one non-archived list per `(household, from_date, to_date)` via partial unique index;
- items generated only from 006 projection lines with `shortfall > 0`, with deterministic order;
- item machine `pending → purchased|skipped`, `skipped → pending`, list machine `open → completed` (zero pending required) → `open` (reopen) and any → `archived` (terminal);
- purchase writes lot + `purchase` movement + item status in one transaction, `source_type = "shopping_item"`, quantity MAY differ from needed;
- optimistic `version` + `expected_version` on every mutation; operation-scoped idempotency receipts replay the stored result and never duplicate lots;
- composite tenant foreign keys and purchased-lot same-household rule;
- Problem Details `401`/`403`/`404`/`409`/`422` in OpenAPI;
- explicit exclusion of plan mutation, consumption, unit conversion, email, and deployment.

T001 is complete. Implementation tasks remain intentionally open until their tests and convergence evidence are complete.
