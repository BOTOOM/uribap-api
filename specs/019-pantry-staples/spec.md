# Feature Specification: Pantry Staple Ingredients

**Feature Branch**: `devin/1791246997-pantry-staples`  
**Created**: 2026-10-06  
**Status**: Draft

## User Scenarios & Testing

### User Story 1 — Mark a household ingredient as a pantry staple (Priority: P1)

A household member marks salt, oil, spices, or another ingredient as a pantry staple. The ingredient
remains in recipes and continues to contribute to forecast demand, but its inventory is not consumed
when a meal is cooked.

**Why this priority**: This flag is the durable source of the behavior required by completion,
forecast, shopping, and plan-detail projections.

**Independent Test**: Create a household ingredient with `pantry_staple=true`, read it back through
REST and MCP, update the flag, and verify a global ingredient cannot be updated.

**Acceptance Scenarios**:

1. **Given** a household member creates an ingredient without the flag, **When** the ingredient is
   retrieved, **Then** `pantry_staple` is `false`.
2. **Given** a household member creates or updates an ingredient with `pantry_staple=true`,
   **When** it is retrieved or listed, **Then** the response contains `pantry_staple: true`.
3. **Given** a global ingredient, **When** a member attempts to set its flag, **Then** the existing
   read-only behavior returns HTTP 403.

### User Story 2 — Cook a recipe without consuming pantry staples (Priority: P1)

A household member records a meal as cooked. Staple ingredients remain part of the recipe but are
not completion lines and create no inventory deductions. The member uses the existing lot-adjustment
flow to record when a staple is finished.

**Independent Test**: Complete recipes containing stocked and empty staples, an all-staple recipe,
and an empty recipe; assert completion lines, movements, errors, and lot balances.

**Acceptance Scenarios**:

1. **Given** a recipe has regular ingredients and pantry staples, **When** it is completed,
   **Then** only regular ingredients are recorded and deducted.
2. **Given** a staple has zero stock, **When** its recipe is completed, **Then** the staple does not
   cause an insufficient-inventory conflict.
3. **Given** every recipe ingredient is a staple, **When** the meal is completed, **Then** it
   succeeds with zero completion lines.
4. **Given** the recipe version has zero ingredients, **When** the meal is completed, **Then** the
   existing “the recipe version has no consumable ingredients” validation error remains.
5. **Given** an explicit completion payload line names a pantry staple, **When** the request is
   validated, **Then** it returns HTTP 422 with detail
   `pantry staple ingredients are not consumed by completions; adjust the lot instead`.

### User Story 3 — Shop for staples only after they run out (Priority: P1)

A member can plan recipes containing staples without treating partial staple stock as a shortage.
When the staple's on-hand amount is zero, forecast and shopping demand include its full recipe
demand.

**Independent Test**: Project recipe demand against positive and zero on-hand quantities and verify
required, optional, total, and shortfall values.

**Acceptance Scenarios**:

1. **Given** a pantry staple has positive on-hand stock below total demand, **When** a forecast is
   requested, **Then** demand is unchanged and shortfall is zero.
2. **Given** a pantry staple has zero on-hand stock, **When** a forecast is requested, **Then**
   shortfall equals total demand and the existing shopping flow can include it.
3. **Given** a non-staple ingredient, **When** a forecast is requested, **Then** its current
   shortage calculation is unchanged.

### User Story 4 — Inspect pantry staples in plan-entry detail (Priority: P2)

A member inspecting a planned meal can distinguish pantry staples from ingredients that need to be
consumed from shared stock.

**Independent Test**: Calculate entry detail with stocked and empty staples alongside repeated
non-staple ingredient/unit rows; verify staple stock is not allocated away from later rows.

**Acceptance Scenarios**:

1. **Given** a staple has positive on-hand stock, **When** entry detail is returned, **Then** its
   `pantry_staple` field is true and shortfall is zero.
2. **Given** a staple has no on-hand stock, **When** entry detail is returned, **Then** shortfall
   equals required amount.
3. **Given** a staple row precedes another row, **When** shared stock is allocated, **Then** the
   staple does not consume `remaining_stock`.

## Requirements

### Functional Requirements

- **FR-001**: The ingredient record MUST persist `pantry_staple` as a non-null Boolean with a
  database server default of false; existing ingredients MUST remain non-staples after migration.
- **FR-002**: Ingredient create requests MUST default the flag to false, update requests MUST allow
  an optional Boolean, and every ingredient response MUST include the Boolean.
- **FR-003**: Global ingredients MUST remain read-only; a request to update a global ingredient's
  pantry flag MUST use the existing HTTP 403 behavior.
- **FR-004**: MCP ingredient create and update tools MUST accept the flag, list MUST return it, and
  the create/update tool descriptions MUST explain its cooking/shopping semantics in one sentence.
- **FR-005**: Completion MUST omit pantry-staple ingredients from planned consumption lines before
  inventory allocation, completion-line persistence, and inventory movement creation.
- **FR-006**: A recipe version with zero ingredients MUST retain the existing no-consumable-
  ingredients validation error; a recipe with one or more ingredients all marked as staples MUST
  complete successfully with zero completion lines.
- **FR-007**: An explicit completion payload line for a pantry staple MUST return HTTP 422
  `validation_error` with detail `pantry staple ingredients are not consumed by completions; adjust
  the lot instead`.
- **FR-008**: Skip/delivery, correction, and reopen behavior MUST remain unchanged; reopen continues
  to operate on the completion's existing lines and movements.
- **FR-009**: Forecast MUST continue calculating required, optional, and total demand for staples;
  for a staple, shortfall MUST equal total demand only when on-hand amount is zero, otherwise zero.
- **FR-010**: Forecast line responses MUST include `pantry_staple`; shopping-list generation MUST
  remain unchanged and continue consuming positive forecast shortfalls.
- **FR-011**: Plan-entry detail MUST include `pantry_staple`; a staple's shortfall MUST equal its
  required amount only when on-hand is zero, and a staple MUST NOT consume shared remaining stock.
- **FR-012**: The canonical OpenAPI document MUST be regenerated using the repository exporter and
  include all changed request and response schemas.
- **FR-013**: The migration MUST be reversible and appended to the current Alembic head
  `6b1354a22e91`.

### Key Entities

- **Ingredient**: Existing household/global catalog entity with a persisted `pantry_staple` flag.
- **Recipe ingredient demand**: Existing required/optional amounts remain part of demand even when
  the ingredient is a staple.
- **Completion consumption line**: Represents only non-staple recipe ingredients that are consumed
  and deducted.
- **Forecast and entry-detail ingredient line**: Exposes pantry status and the server-computed
  shortage without changing recipe demand.

## Success Criteria

- **SC-001**: Ingredient create, get, update, and MCP list/create/update preserve the pantry flag;
  global updates remain forbidden.
- **SC-002**: Cooking a recipe with stocked or empty staples creates no staple completion line,
  movement, or deduction; all-staple recipes succeed with zero lines.
- **SC-003**: Empty recipes preserve their existing validation error, while an explicit staple line
  returns the exact specified 422 detail.
- **SC-004**: Positive-stock staples have zero forecast shortfall even when demand exceeds stock;
  zero-stock staples have shortfall equal to total demand; non-staple behavior is unchanged.
- **SC-005**: Plan-entry detail exposes the flag and required-amount shortfall rule without
  allocating staple stock to other rows.
- **SC-006**: Tests cover the reversible migration and end-to-end PostgreSQL behavior; generated
  OpenAPI matches the implemented contract.
