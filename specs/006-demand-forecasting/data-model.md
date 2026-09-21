# Data Model: Demand Forecasting

No new tables. The projection is computed on read from existing schema.

## Inputs read

- `meal_plan` (state = `approved`, household-scoped) and `meal_plan_entry` rows whose `planned_date` is inside `[from_date, to_date]`. Entries carry `recipe_version_id` and `servings`.
- `recipe_version` (`base_servings`) and `recipe_version_ingredient` (`ingredient_id`, `amount`, `unit`, `optional`, `position`) for the pinned versions.
- `ingredient` (`id`, `name`) for display names only — never for math.
- `inventory_lot` rows for the household with `available = true`, `quantity_on_hand > 0`, and `expiration_date IS NULL OR expiration_date >= from_date`, grouped by `(ingredient_id, unit)`.

## Projection line (computed, not persisted)

Per `(ingredient_id, unit)`:

- `required_amount`: sum of `amount * (servings / base_servings)` over non-optional ingredients, `Decimal` quantized `0.000001` `ROUND_HALF_UP`.
- `optional_amount`: same for `optional = true` ingredients.
- `total_amount = required_amount + optional_amount`.
- `on_hand_amount`: sum of qualifying lot quantities for the same `(ingredient_id, unit)`.
- `shortfall_amount = max(0, total_amount - on_hand_amount)`.

## Invariants

- Lines with `total_amount = 0` MUST NOT be emitted.
- Two different units of the same ingredient MUST produce two lines; no conversion.
- Line ordering MUST be deterministic (sorted by ingredient name, then unit, then ingredient id).
- The projection MUST NOT write to any table and MUST NOT depend on wall-clock time beyond the caller-supplied/defaulted window.
