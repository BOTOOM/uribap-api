# Feature Specification: Completed Meal Outcomes and Plan Entry Detail

**Feature Branch**: `devin/1790817968-exclude-completed-forecast`
**Status**: Ready for implementation

## User Scenarios & Testing

### User Story 1: Resolved meals no longer create demand (Priority: P1)

A household member records a planned meal as cooked. Its future forecast and shopping demand no
longer include the entry because the meal has been resolved.

**Independent Test**: Approve a plan with one meal, record its completion, and request a forecast
covering that date. The approved plan remains traceable, but the completed entry contributes no
ingredient demand or shortfall.

**Acceptance Scenarios**:

1. **Given** an approved plan entry without a recorded completion, **When** demand is forecast for
   its date, **Then** the entry contributes its scaled recipe ingredients.
2. **Given** that same entry has a recorded cooked completion, **When** demand is forecast again,
   **Then** the completed entry contributes no demand.
3. **Given** a completed entry and another uncompleted entry in the same approved plan, **When**
   demand is forecast, **Then** only the uncompleted entry contributes demand.
4. **Given** a completion from another household for an entry with the same date, **When** demand
   is forecast, **Then** it has no effect on the requesting household.
5. **Given** every entry in an approved plan is resolved, **When** demand is forecast, **Then** the
   plan remains in `considered_plan_ids` and the forecast items are empty.
6. **Given** a recorded completion is reopened, **When** demand is forecast again, **Then** the
   entry contributes its planned demand again.

### User Story 2: Record a meal that was not cooked at home (Priority: P1)

A household member marks an approved plan entry as skipped because the household ordered delivery,
ate out, or did not prepare the meal. The meal is recorded for history but does not consume
inventory. The household can reopen the completion if it was recorded by mistake.

**Independent Test**: Skip an approved entry with a reason, confirm the completion is recorded with
the skipped outcome and no inventory effects, then reopen it and confirm its demand returns.

**Acceptance Scenarios**:

1. **Given** an approved plan entry without a recorded completion, **When** a household member skips
   it with an optional reason, **Then** the API returns `201` with a recorded completion whose
   outcome is `skipped` and whose outcome note is the supplied reason.
2. **Given** a skipped entry, **When** its completion is recorded, **Then** the completion has no
   lines, no inventory movement is created, and inventory lot quantities do not change.
3. **Given** a plan that is not approved, **When** a member tries to skip an entry, **Then** the API
   returns `409`.
4. **Given** an entry outside the requested household or plan, **When** a member tries to skip it,
   **Then** the API returns `404`.
5. **Given** an entry with an existing recorded cooked or skipped completion, **When** a member tries
   to skip it again, **Then** the API returns `409`.
6. **Given** a request with an `Idempotency-Key`, **When** the same skip request is replayed, **Then**
   the API returns the original response without creating duplicate completion or audit data.
7. **Given** a skipped completion, **When** it is reopened, **Then** its state becomes `reopened`
   and the plan entry contributes demand again.
8. **Given** a cooked completion, **When** its response is read, **Then** its outcome is `cooked`.
9. **Given** an entry has a recorded skipped completion, **When** demand is forecast, **Then** the
   entry contributes no demand.
10. **Given** an MCP client lists plan tools, **When** it discovers the skip action, **Then**
   `uribap_skip_meal` is a WRITE tool titled "Mark meal as not cooked" with the specified skip
   behavior description, and the cooked completion tool describes forecast/shopping exclusion.

### User Story 3: See what is needed to prepare a planned meal (Priority: P1)

A household member or connected client requests one plan entry's preparation details in one
read-only call. The response shows the scaled ingredient amounts, available household stock,
shortfalls, recipe description, and any current recorded completion.

**Independent Test**: Request detail for an approved entry with servings different from its recipe
base, matching available and unavailable inventory lots, and a recipe description. Verify the
scaled lines, stock and shortfall values, optional flags, ordering, and recipe description.

**Acceptance Scenarios**:

1. **Given** an entry with 4 servings and a recipe version based on 2 servings, **When** its detail
   is requested, **Then** each recipe ingredient amount is doubled using the completion service's
   planned-line scaling.
2. **Given** available and unavailable lots for an ingredient, **When** entry detail is requested,
   **Then** only available lots in the same household, ingredient, and unit contribute to
   `on_hand_amount`, and `shortfall_amount` is never negative.
3. **Given** a recipe with a description and ordered optional and required ingredients, **When**
   detail is requested, **Then** the description and each line's optional flag and recipe position
   are returned.
4. **Given** a current recorded completion, **When** detail is requested, **Then** its completion
   response is embedded; **When** it has been reopened, **Then** `completion` is `null`.
5. **Given** a plan or entry belonging to another household, **When** detail is requested, **Then**
   the API returns `404` and does not disclose its data.
6. **Given** any valid entry detail request, **When** the endpoint is called, **Then** no plan,
   completion, or inventory data is mutated.
7. **Given** an MCP client lists plan tools, **When** it discovers entry detail, **Then**
   `uribap_get_plan_entry` is a READ_ONLY tool titled "Plan entry detail" and returns the same
   detail payload.

### Edge Cases

- A completion outside the requested forecast window must not affect entries inside the window.
- Reopened completion history does not suppress demand when no recorded completion exists.
- An older reopened completion does not restore demand if a newer completion is recorded.
- Skipped completions are recorded completions for forecast exclusion, despite having no lines.
- Correcting a line on a skipped completion remains impossible because it has no lines.
- Forecasting remains read-only and deterministic.

## Requirements

### Functional Requirements

- **FR-001**: Forecast demand MUST exclude an approved plan entry when that entry has a
  household-scoped completion in the `recorded` state, regardless of completion outcome.
- **FR-002**: A `reopened` completion MUST NOT exclude its plan entry from forecast demand.
- **FR-003**: If an entry has any current `recorded` completion, older reopened completion history
  MUST NOT cause the entry to contribute demand.
- **FR-004**: Completion exclusion MUST be scoped by both household and plan entry.
- **FR-005**: Approved plans containing completed entries MUST remain traceable in
  `considered_plan_ids`; only completed entries are removed from demand aggregation.
- **FR-006**: Shopping-list generation MUST inherit the corrected behavior through the canonical
  forecast and MUST NOT implement a separate completion filter.
- **FR-007**: The change MUST preserve forecast window validation, recipe scaling, optional demand,
  unit grouping, inventory comparison, deterministic ordering, and read-only behavior.
- **FR-008**: Meal completion MUST distinguish the `cooked` and `skipped` outcomes while retaining
  the existing `recorded` and `reopened` lifecycle states.
- **FR-009**: Existing completion rows MUST receive the `cooked` outcome when the new outcome
  column is added; the persistence model MUST constrain outcomes to `cooked` or `skipped`.
- **FR-010**: `POST /api/v1/plans/{plan_id}/entries/{entry_id}/skip` MUST accept an optional reason
  of at most 2000 characters and support the same `Idempotency-Key` receipt and fingerprint
  behavior as the complete endpoint, using operation `meal_entry_skip`.
- **FR-011**: Skipping MUST require an existing approved plan and an entry scoped to both the plan
  and household; violations MUST use the existing 404 and 409 domain errors.
- **FR-012**: A successful skip MUST create a `recorded` completion with outcome `skipped`, preserve
  the reason as `outcome_note`, create no completion lines or inventory movements, and leave lot
  quantities unchanged.
- **FR-013**: A successful skip MUST record a `MEAL_COMPLETED` event with `meal_plan_entry_id`,
  `line_count: 0`, and `outcome: "skipped"`; cooked completion events MUST include
  `outcome: "cooked"`.
- **FR-014**: `MealCompletionResponse` MUST include `outcome` and `outcome_note` for cooked,
  skipped, and reopened completions.
- **FR-015**: Reopening a skipped completion MUST succeed without reversing inventory and MUST make
  the entry eligible for forecast demand again.
- **FR-016**: `GET /api/v1/plans/{plan_id}/entries/{entry_id}/detail` MUST return the plan entry's
  plan state, scheduled date/type, servings, notes, pinned recipe/version metadata, ordered
  ingredient lines, and current recorded completion or `null`.
- **FR-017**: Entry detail MUST return the recipe description as `recipe_description` and MUST NOT
  substitute a separate instruction model for that field.
- **FR-018**: Detail ingredient `required_amount` MUST use `planned_lines` from the completion
  domain, with the entry's servings and version's base servings.
- **FR-019**: Detail `on_hand_amount` MUST sum available inventory lots for the same household,
  ingredient, and unit. `shortfall_amount` MUST be `max(0, required_amount - on_hand_amount)`.
- **FR-020**: Detail ingredient lines MUST include ingredient id/name, unit, optional flag, and
  recipe position, ordered by recipe position then id.
- **FR-021**: Detail reads MUST be tenant-scoped, return `404` for a foreign plan or entry, and
  MUST NOT mutate persisted state.
- **FR-022**: The migration MUST be additive and reversible, use down revision
  `f2b8d4e6a917`, and set a server default that backfills existing completion rows as `cooked`.
- **FR-023**: The new skip and detail endpoints and completion response fields MUST appear in the
  generated OpenAPI artifact; that artifact MUST be generated by the repository tool.
- **FR-024**: MCP MUST expose `uribap_skip_meal` as WRITE with title "Mark meal as not cooked" and
  description "Record that a planned meal was not cooked at home (delivery, ate out, skipped).
  Removes it from forecast and shopping demand without touching inventory. Reopen the completion
  to undo."; expose `uribap_get_plan_entry` as READ_ONLY with title "Plan entry detail"; and state
  in the cooked-completion tool description that cooked meals leave forecast and shopping demand.

### Key Entities

- **Meal plan entry**: A dated recipe occurrence that contributes demand while pending.
- **Meal completion**: Auditable record with a `recorded` or `reopened` lifecycle state and a
  `cooked` or `skipped` outcome. Any recorded outcome suppresses future demand; reopening restores
  demand. A skipped completion has a reason but no consumed lines.
- **Demand forecast**: Read-only projection used directly by shopping-list generation.
- **Plan entry detail**: Read-only projection of pinned recipe requirements, same-unit available
  stock, shortfalls, and the current recorded completion.

## Assumptions

- The completion subsystem enforces at most one `recorded` completion per household plan entry.
- Existing recorded completions represent meals already cooked and are backfilled as `cooked`.
- Available inventory lots and recipe lines use the existing household, ingredient, and unit
  constraints.
- Existing shopping lists are snapshots and are not retroactively rewritten; newly generated lists
  use the corrected forecast.

## Success Criteria

- **SC-001**: Cooked and skipped recorded entries contribute exactly zero demand; reopening restores
  the entry's original scaled demand.
- **SC-002**: Mixed plans forecast every pending entry and exclude every recorded entry, while
  preserving all approved plan identifiers.
- **SC-003**: Skipping changes completion/audit state only: no completion lines, inventory
  movements, or lot quantity changes occur.
- **SC-004**: One plan-entry detail response provides correctly scaled requirements, same-unit
  available stock and shortfalls, recipe description, and recorded completion state.
- **SC-005**: Tenant isolation, idempotency, migration round-trip, generated OpenAPI, and the full API
  suite pass.
