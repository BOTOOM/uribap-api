# Research: Completed Meal Outcomes and Plan Entry Detail

## Decision: Filter every recorded completion at forecast entry selection

Use a correlated household-scoped `NOT EXISTS` condition when selecting plan entries for
projection. A plan entry contributes demand only when no completion exists for the same household
and entry in the `recorded` state. The outcome (`cooked` or `skipped`) does not change this rule.

### Rationale

- It preserves the distinction between approved plan traceability and pending entry demand.
- It handles reopened completions naturally because only `recorded` rows suppress demand.
- It avoids per-entry database queries and keeps shopping generation on the canonical forecast path.
- It relies on the existing partial unique index for recorded completions and the indexed entry key.
- `demand_forecast` collects approved plan identifiers before selecting entries, so the anti-join
  leaves `considered_plan_ids` unchanged even when no entry contributes demand.

### Alternatives considered

- **Subtract actual completion lines from projected demand**: Rejected because the completed meal is
  historical consumption, not remaining demand, and actual ingredients may differ from the recipe.
- **Remove or archive the plan entry during completion**: Rejected because it destroys plan history
  and violates the completion feature's separation from planning state.
- **Filter completed entries only in shopping generation**: Rejected because direct forecasts and
  MCP forecasts would remain wrong and business rules would diverge.
- **Filter by completion timestamp or planned date**: Rejected because entry identity and state are
  the authoritative completion relationship.

## Decision: Preserve considered plan identifiers

Approved plans remain in `considered_plan_ids` even if every entry in the requested window is
completed.

### Rationale

The response documents which approved plans were examined. Completion changes entry demand, not the
set of approved plans overlapping the window.

### Alternatives considered

- **Omit plans with no pending entries**: Rejected because it weakens traceability and changes
  existing response semantics unnecessarily.

## Decision: Model skipped as an outcome on the existing completion lifecycle

Keep `recorded` and `reopened` as lifecycle state and add an independent `cooked` or `skipped`
outcome. Add nullable `outcome_note` to preserve why a meal was skipped. Existing completion rows
are cooked and receive the `cooked` database default during the additive migration.

### Rationale

- It records delivery, eating out, and not-prepared outcomes without pretending ingredients were
  consumed or mutating inventory.
- A skipped completion remains an auditable `recorded` completion, so the same forecast anti-join
  excludes it without outcome-specific demand logic.
- Reopening already works by reversing completion lines; an empty line list makes that behavior a
  safe no-op for skipped meals while returning demand.
- A check constraint keeps persisted outcome values aligned with the domain enum.

### Alternatives considered

- **Add `skipped` to the lifecycle state**: Rejected because it would conflate whether a completion
  is current or reopened with what happened to the meal.
- **Create zero-amount completion lines or inventory movements**: Rejected because these would
  falsely describe stock consumption and conflict with positive line constraints.
- **Delete or alter the plan entry**: Rejected because it would lose plan history and bypass
  completion audit semantics.

## Decision: Reuse completion scaling for plan-entry detail

`get_entry_detail` builds `RecipeIngredientInput` values from the pinned
`RecipeVersionIngredient` rows and calls the existing `planned_lines(ingredients, servings,
base_servings)` domain policy. Its `planned_amount` is the response's scaled `required_amount`.

### Rationale

- The completion path already uses `planned_lines` for the same pinned recipe version and servings.
- Reuse preserves Decimal quantization, scale validation, zero-line handling, and quantity
  semantics instead of introducing a second scaling formula.
- Detail's stock comparison remains a read-only aggregate of same-household, same-ingredient,
  same-unit lots whose `available` flag is true; shortfall is `max(0, required - on_hand)`.

## Decision: Tenant-scope detail and embed only a current recorded completion

Resolve the plan by both `plan_id` and membership household, then resolve the entry by both
`entry_id`, `plan_id`, and household. Return `404` for a missing or foreign resource. Embed
`MealCompletionResponse` only for a `recorded` completion; return `null` for no completion or a
reopened completion.

### Rationale

- It matches existing planning and completion tenant boundaries and does not disclose foreign
  identifiers.
- Reopened completions are history, not current status; the plan entry is pending again.
- The recipe description is the requested preparation copy; no separate instruction model is
  substituted.

## Decision: Add migration and generated contract updates

Add one Alembic revision after the verified single head `f2b8d4e6a917`. Add outcome columns with a
server default of `cooked` so existing rows remain valid. Regenerate `openapi/openapi.json` with
`uribap_api.tools.export_openapi` because response fields and both endpoints are public contract
changes.

### Rationale

The outcome is new persisted domain data and the skip/detail routes expand the REST contract.
Hand-editing the generated OpenAPI file would bypass its repository source of truth.
