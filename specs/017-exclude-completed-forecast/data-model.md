# Data Model: Completed Meal Outcomes and Plan Entry Detail

One additive migration extends `meal_completion`; no new tables are required.

## Existing relationships used

### MealPlanEntry

- Belongs to one household and one meal plan.
- Pins one recipe version and planned serving count.
- Contributes demand only while it has no current recorded completion.

### MealCompletion

- Belongs to the same household as its plan entry.
- References exactly one meal plan entry.
- `state` remains `recorded` or `reopened`; it describes whether the completion is current.
- `outcome` is `cooked` or `skipped`; it describes what happened to the meal independently of
  lifecycle state.
- `outcome_note` is nullable text containing the optional skip reason.
- A cooked completion contains the existing completion lines and inventory movements.
- A skipped completion is recorded with no completion lines or inventory movements.
- A reopened completion does not suppress projected demand, regardless of its outcome.
- The existing partial unique index allows at most one recorded completion per household entry.

### Migration

- Revision: new feature 017 revision.
- `down_revision`: `f2b8d4e6a917` (verified current single Alembic head).
- Add non-native enum `outcome` as non-null with Python default `COOKED` and database
  `server_default='cooked'`; the server default backfills existing rows.
- Add nullable `outcome_note` as `Text`.
- Add check constraint `ck_meal_completion_outcome` restricting values to `cooked` and `skipped`.
- Downgrade drops the constraint and both columns.

## Plan-entry detail projection

The response is assembled from existing tenant-owned rows and does not persist a snapshot:

- `MealPlan` and `MealPlanEntry` provide plan state, scheduled date/type, servings, notes, and
  pinned recipe version.
- `Recipe` provides name and description; `RecipeVersion` provides version number, base servings,
  and preparation minutes.
- Ordered `RecipeVersionIngredient` rows provide ingredient ids, units, optional flags, and
  positions. `planned_lines` scales their amounts using the entry's servings and the version's base
  servings; its `planned_amount` becomes `required_amount`.
- Available same-household `InventoryLot` rows are aggregated by ingredient id and unit for
  `on_hand_amount`.
- `shortfall_amount = max(0, required_amount - on_hand_amount)`.
- A current recorded `MealCompletion` is expanded with the existing completion response builder;
  no completion or a reopened completion produces `completion: null`.

## Forecast selection invariant

For an approved entry \(e\) in household \(h\):

\[
\operatorname{pending}(e,h) =
\neg\exists c\;(c.meal\_plan\_entry\_id=e.id
\land c.household\_id=h
\land c.state=\text{recorded})
\]

The recorded-state predicate is independent of `outcome`; both cooked and skipped completions
exclude demand. Only entries without a current recorded completion proceed to recipe scaling and
ingredient aggregation.
