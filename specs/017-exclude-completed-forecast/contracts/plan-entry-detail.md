# Plan Entry Detail Contract

## Endpoint

`GET /api/v1/plans/{plan_id}/entries/{entry_id}/detail`

The endpoint is read-only and requires an active household membership. It returns `404` when the
plan or entry is absent or belongs to another household, or when the entry does not belong to the
requested plan.

## Response

`MealPlanEntryDetailResponse` contains:

- `entry_id`, `plan_id`, `plan_state`, `planned_date`, `meal_type`, `servings`, and `notes`
- `recipe_id`, `recipe_name`, nullable `recipe_description`
- `recipe_version_id`, `version_number`, `base_servings`, and `prep_minutes`
- `ingredients`: ordered list of `MealPlanEntryIngredientLine` containing `ingredient_id`,
  `ingredient_name`, Decimal `required_amount`, `unit`, `optional`, Decimal `on_hand_amount`,
  Decimal `shortfall_amount`, and `position`
- `completion`: current recorded `MealCompletionResponse`, or `null` when there is no current
  recorded completion

Amounts use the completion domain's `planned_lines` scaling for entry servings versus recipe
version base servings. On-hand quantities start from the sum of available, positive inventory
lots matching household, ingredient, and unit that are not expired on
`max(local_today, planned_date)`. Lines sharing an ingredient and unit draw from that stock in
recipe order (position, ingredient id, row id): each line's `on_hand_amount` is what remains after
earlier lines took `min(required_amount, remaining)`, so the same stock is never counted twice.
Shortfall is `max(0, required_amount - on_hand_amount)`. The recipe
description is returned as preparation copy; this endpoint does not mutate plan, completion, or
inventory state.

## MCP tool

`uribap_get_plan_entry(plan_id, entry_id)` is a READ_ONLY tool titled `"Plan entry detail"` and
returns the same detail payload.
