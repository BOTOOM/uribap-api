# Feature Specification: Inventory Ledger

**Feature Branch**: `004-inventory-ledger`  **Status**: Ready for implementation

## User Stories

- **US1 (P1)**: A household member records pantry/refrigerator/freezer lots with Decimal quantity, unit, expiry, and location.
- **US2 (P1)**: A member adjusts a lot through an append-only movement ledger; balance never becomes negative.
- **US3 (P1)**: Replaying an operation with the same idempotency key returns the original safe result and does not duplicate a movement.
- **US4 (P2)**: A member sees current stock grouped by ingredient and lot, including expired/unavailable state.

## Requirements

- **FR-001**: `inventory_lot.quantity_on_hand` MUST use NUMERIC/Decimal and MUST be non-negative.
- **FR-002**: Every balance mutation MUST create an append-only `inventory_movement` with actor, type, source, and idempotency key where supplied.
- **FR-003**: Movement types MUST include `purchase`, `meal_consumption`, `manual_adjustment`, `waste`, and `reversal`.
- **FR-004**: A negative movement MUST be rejected when it exceeds available balance.
- **FR-005**: Inventory MUST be tenant-isolated by active household membership.
- **FR-006**: Idempotent replay MUST not mutate balance twice.
- **FR-007**: Lot location MUST be `pantry`, `refrigerator`, or `freezer`; units MUST match ingredient dimension.
- **FR-008**: API errors MUST use Problem Details and conflict/validation statuses.
- **FR-009**: No forecast or shopping calculation belongs in the ledger.

## Acceptance

- Two concurrent adjustments serialize safely and never produce negative balance.
- Reconciliation from movements equals cached lot balance.
- Cross-household lot access is denied.
- Expiry and unavailable lots remain queryable but are excluded from available balance.

## Out of scope

Email delivery, deployment, forecasting, shopping, and meal completion orchestration.
