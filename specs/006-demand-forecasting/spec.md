# Feature Specification: Deterministic Demand Forecasting

**Feature Branch**: `006-demand-forecasting`  **Status**: Ready for implementation

## User Stories

- **US1 (P1)**: A household member asks what ingredients the approved plan needs over a date window; the API returns projected demand aggregated per ingredient and unit.
- **US2 (P1)**: The member sees projected demand against current on-hand inventory and a deterministic shortfall per line, so they know what is missing before shopping.
- **US3 (P1)**: Recomputing the same window against unchanged inputs MUST return identical results — projection is deterministic and read-only.
- **US4 (P2)**: Optional recipe ingredients are reported separately from required amounts so shopping can decide whether to include them.
- **US5 (P2)**: Ingredients demanded in different units appear as separate lines; no implicit unit conversion is performed.

## Requirements

- **FR-001**: Demand MUST be projected only from entries of `approved` meal plans whose `planned_date` falls inside the requested window `[from_date, to_date]`; `draft`, `proposed`, and `archived` plans MUST NOT contribute.
- **FR-002**: Each entry scales its pinned recipe version's ingredient amounts by `servings / base_servings`, computed with `Decimal` quantized to six places (`ROUND_HALF_UP`); `base_servings <= 0` MUST raise a domain error.
- **FR-003**: Aggregation MUST group by `(ingredient_id, unit)`; lines with different units MUST NOT be merged or converted.
- **FR-004**: Each line MUST carry `required_amount` (non-optional contributions) and `optional_amount` (optional contributions) separately, plus `total_amount = required + optional`.
- **FR-005**: On-hand MUST sum `inventory_lot.quantity_on_hand` for lots that are `available`, have `quantity_on_hand > 0`, and are not expired at `from_date` (`expiration_date IS NULL OR expiration_date >= from_date`), grouped by `(ingredient_id, unit)`.
- **FR-006**: `shortfall_amount = max(0, total_amount - on_hand_amount)` per line; a line with zero total demand MUST NOT appear in the response.
- **FR-007**: The endpoint MUST be read-only: no writes to plans, entries, lots, movements, or any table; no `expected_version` and no `Idempotency-Key`.
- **FR-008**: `from_date` MUST default to the server's current date and `to_date` to `from_date + 6` days when omitted; `from_date <= to_date` MUST hold and the window MUST NOT exceed 62 days (`422` otherwise).
- **FR-009**: The response MUST echo the effective window and the ids of the approved plans considered, so clients can trace a projection back to its inputs.
- **FR-010**: The projection MUST be deterministic: identical inputs produce identical output; the response MUST NOT embed volatile fields such as generation timestamps.
- **FR-011**: Errors MUST use Problem Details with `401`, `403`, and `422` documented in OpenAPI.
- **FR-012**: Shopping-list generation, purchase tracking, preparation derivation, and consumption posting MUST NOT live in this feature.

## Acceptance

- An approved plan with two entries scales both recipes by their serving factors and merges the same ingredient+unit into one line.
- A `draft` plan contributes nothing; after approval its entries appear in the next request.
- A lot that expired before `from_date` does not count toward on-hand; the line's shortfall grows accordingly.
- Two identical requests return byte-identical payloads.
- A demand line in `g` and an on-hand lot in `kg` produce separate lines, never a conversion.

## Out of scope

Shopping projection/list, purchases, preparation tasks, meal completion or consumption posting, unit conversion, email delivery, notifications, and deployment.
