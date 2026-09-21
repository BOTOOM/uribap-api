# Spec Kit Analysis: Meal Planning

**Status**: PASS — the analysis gate is complete.

## Resolved contradictions (review round 1)

The first review round surfaced three spec/contract mismatches that are now resolved:

- **`expected_version` scope**: FR-002 originally demanded it on every mutation, but plan creation has no prior version. FR-002 and US3 now scope it to mutations of an existing plan; concurrent creation is serialized by the unique partial index on `(household_id, week_start_date)`.
- **`approved` reopen**: FR-003 called `approved` terminal while the contract allowed `approved → draft`. FR-003, US4, and the contract now agree: `approved` MAY return to `draft` only via `reopen` with a mandatory note; `archived` remains the only terminal state.
- **PATCH field set**: US2 allows updating the pinned recipe version, but PATCH omitted `recipe_version_id`. The contract now lists it with the same published-version validation, and defines explicit `notes: null` as clearing the note.

## Current consistency

The spec, plan, data model, contract, traceability, checklist, and tasks agree on:

- optimistic integer `version` with `expected_version` on every mutation of an existing plan;
- state machine `draft → proposed → approved`, `proposed|approved → draft` reopen (note required from `approved`), and terminal `archived`;
- approver MUST differ from proposer when the household has at least two active members, and a missing proposer cannot be approved in that case;
- append-only `meal_plan_state_event` and operation-scoped idempotency receipts with request hash and stored original result payload;
- composite tenant foreign keys and a partial unique index for one active plan per household-week;
- entries pin published recipe versions and planning never mutates inventory;
- Problem Details and OpenAPI error coverage;
- explicit exclusion of email delivery, notifications, deployment, and forecasting math.

T001 is complete. Implementation tasks remain intentionally open until their tests and convergence evidence are complete.
