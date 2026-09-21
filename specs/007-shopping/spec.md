# Feature Specification: Shopping Projection and Purchases

**Feature Branch**: `007-shopping`  **Status**: Ready for implementation

## User Stories

- **US1 (P1)**: A household member generates a shopping list from the deterministic demand projection for a date window; only lines with a shortfall become items.
- **US2 (P1)**: The member marks an item purchased by recording quantity, unit, location, and expiration; the API creates an inventory lot and a `purchase` movement in the same transaction.
- **US3 (P1)**: The member skips an item they will not buy and can restore it to pending.
- **US4 (P1)**: Every mutation of an existing list carries `expected_version`; a stale writer receives `409` and no partial change is applied.
- **US5 (P2)**: The list is completed only when no pending items remain; a completed list can reopen; archiving is terminal.
- **US6 (P2)**: Replaying a purchase with the same idempotency key returns the original result without duplicating the lot or movement.

## Requirements

- **FR-001**: `shopping_list` MUST be tenant-isolated by household, carry `from_date`/`to_date` of the projection window, an integer `version` incremented transactionally on every mutation, and state `open`, `completed`, or `archived`.
- **FR-002**: Generation MUST reuse the deterministic demand projection (006): `approved`-plan entries in the window, `Decimal` scaling, per-`(ingredient, unit)` aggregation, and the on-hand rule. Each projected line with `shortfall_amount > 0` MUST create one `shopping_item` with `needed_amount = shortfall_amount`, the line's `optional_amount`, and `status = pending`. A window projecting zero shortfall MUST create an empty list, not an error.
- **FR-003**: `shopping_item` MUST keep `needed_amount` (`NUMERIC(18,6)`), `unit`, `ingredient_id`, `status`, `position`, and purchase fields (`purchased_amount`, `purchased_lot_id`, `purchased_at`). Items MUST be mutable only while the list is `open`.
- **FR-004**: Purchasing an item MUST, in one transaction: create an `inventory_lot` for the household with the purchased `quantity`/`unit`/`location`/optional `expiration_date`, append an `inventory_movement` of type `purchase` with `source_type = "shopping_item"` and `source_id = item_id`, and mark the item `purchased` with `purchased_amount` and `purchased_lot_id`. Purchased quantity MAY differ from `needed_amount`.
- **FR-005**: Item status transitions MUST be `pending → purchased` (via purchase), `pending → skipped` (skip), `skipped → pending` (restore). No other transitions are legal (`409`).
- **FR-006**: List transitions MUST be `open → completed` only when zero items are `pending` (`409` otherwise), `completed → open` (reopen), and `open|completed → archived` (terminal). Every transition MUST bump the version.
- **FR-007**: Every mutation of an existing list or its items MUST require `expected_version`; mismatch MUST return `409` with no partial writes.
- **FR-008**: `Idempotency-Key` MUST be accepted on all mutations; replay semantics match planning/inventory (operation + request hash + stored original result; different hash → `409`). A replayed purchase MUST NOT create a second lot or movement.
- **FR-009**: Items and receipts MUST enforce composite household-scoped foreign keys; a `shopping_item`'s `purchased_lot_id` MUST reference a lot of the same household.
- **FR-010**: Errors MUST use Problem Details with `401`, `403`, `404`, `409`, and `422` documented in OpenAPI.
- **FR-011**: Only one non-archived shopping list per household per `(from_date, to_date)` window MUST exist (`409` on duplicate generation).
- **FR-012**: Shopping MUST NOT mutate meal plans or their entries; consuming purchases is phase 009. Email and notifications are out of scope.

## Acceptance

- Generating a list from a window with shortfalls creates one pending item per shortfall line, ordered deterministically.
- Purchasing an item creates the lot and `purchase` movement and flips the item to `purchased`; the projection's next run counts the new lot toward on-hand.
- A list with pending items cannot complete; after all items resolve it completes and can reopen.
- Replaying a purchase returns the stored result; a same-key different-body request returns `409`.
- A second generation for the same window returns `409` while the first list is not archived.

## Out of scope

Preparation derivation, meal completion/consumption posting, unit conversion between demanded and purchased units (purchase unit MUST match the item unit), email delivery, notifications, and deployment.
