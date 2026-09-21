# Feature Specification: Meal Planning and Collaboration

**Feature Branch**: `005-meal-planning`  **Status**: Ready for implementation

## User Stories

- **US1 (P1)**: A household member creates a meal plan for a week (Monday `week_start_date`); the plan starts as `draft`.
- **US2 (P1)**: Members add, update, and remove planned meals (planned date, meal type, published recipe version, servings, position) while the plan is editable.
- **US3 (P1)**: Every mutation carries `expected_version`; a stale writer receives `409` and must reload before retrying.
- **US4 (P1)**: A member proposes the plan and a different member approves it; when the household has more than one active member, the approver MUST differ from the proposer. Any member can return a proposed plan to `draft`.
- **US5 (P2)**: Plan entries pin a specific published recipe version, so later recipe edits never rewrite the plan's historical truth.
- **US6 (P2)**: A member can archive a plan; archived plans remain readable for audit.

## Requirements

- **FR-001**: `meal_plan` MUST be tenant-isolated by household and carry an integer `version` incremented transactionally on every mutation.
- **FR-002**: Every mutation MUST require `expected_version`; a mismatch MUST return `409` and MUST NOT apply partial changes.
- **FR-003**: Plan states MUST be `draft`, `proposed`, `approved`, `archived`. Entries are editable only in `draft`. `proposed` locks entries pending approval. `approved` is the terminal active state. `archived` is terminal.
- **FR-004**: Entries MUST reference a `published` recipe version, a `planned_date` inside the plan week, a `meal_type` from the recipe domain enum, `servings > 0`, and a `position`.
- **FR-005**: Planning MUST NOT mutate inventory lots, movements, or balances; it is projected demand only.
- **FR-006**: Every state transition MUST append a `meal_plan_state_event` row with actor, from/to state, and UTC timestamp; events are append-only.
- **FR-007**: `Idempotency-Key` MUST be accepted on all mutations; replay semantics match the inventory ledger (operation + request hash + stored original result; different hash → `409`).
- **FR-008**: Errors MUST use Problem Details with `401`, `403`, `404`, `409`, and `422` documented in OpenAPI.
- **FR-009**: Entries and events MUST enforce composite household-scoped foreign keys like the inventory ledger.
- **FR-010**: Only one non-archived plan per household per `week_start_date` MUST exist.
- **FR-011**: Demand projection/forecasting MUST NOT live in this feature; the plan only records intent.

## Acceptance

- Two members editing concurrently serialize on `version`; the loser gets `409` and no partial write.
- A proposed plan cannot gain entries until it returns to `draft`.
- In a two-member household, the proposer cannot approve their own proposal; the other member can.
- Replaying an entry creation with the same idempotency key returns the original entry without duplicating it.
- Archived plans are excluded from the current-plan lookup but remain fetchable by id.
- No inventory row changes when plan entries are created, edited, approved, or archived.

## Out of scope

Email delivery, notifications, deployment, demand forecasting math, shopping projection, preparation derivation, and meal completion/consumption.
