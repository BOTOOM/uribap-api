# Completion API Contract

Base path: `/api/v1`. Every route requires a bearer token, active membership, and
`X-Household-ID` (UUID). Mutations accept `Idempotency-Key` (max 128); mutations on
an existing completion require `expected_version`.

## `POST /plans/{plan_id}/entries/{entry_id}/complete`

Request: `{lines?: [{ingredient_id, actual_amount, unit}]}`. The plan MUST be
`approved`. Omitting `lines` uses the planned amounts (recipe scale factor);
explicit lines MUST cover every non-optional recipe ingredient and may add
optional ones. Response `201`: `MealCompletionResponse`. `409` insufficient stock
or entry already completed; `404` unknown plan/entry; `422` invalid payload.

## `GET /meal-completions`

Query: `entry_id`, `state` (`recorded`/`reopened`), `from`, `to` (ISO datetimes on
`completed_at`). Response `200`: `MealCompletionPage` `{items}` ordered by
`completed_at DESC, id`.

`MealCompletionResponse` `{id, state, version, meal_plan_entry_id, planned_date,
meal_type, recipe_version_id, recipe_name, lines:[MealCompletionLineResponse],
completed_by_user_id, completed_at, reopened_by_user_id, reopened_at,
reopen_reason, created_at, updated_at}`.

`MealCompletionLineResponse` `{id, ingredient_id, ingredient_name, planned_amount,
actual_amount, unit, optional, position}`.

## `GET /meal-completions/{completion_id}`

Response `200`: `MealCompletionResponse`. `404` unknown/cross-household.

## `POST /meal-completions/{completion_id}/lines/{line_id}/correct`

Request: `{expected_version, actual_amount, unit}`. `unit` MUST equal the line
unit. Writes reversal + new consumption movements and updates the line.
Response `200`: `MealCompletionResponse`. `404` unknown ids; `409` illegal state or
version mismatch or insufficient stock for the corrected amount; `422` invalid
payload.

## `POST /meal-completions/{completion_id}/reopen`

Request: `{expected_version, reason?}`. Writes reversal movements for every line
movement and marks the completion `reopened`. Response `200`:
`MealCompletionResponse`. `404`/`409` as above.

## Error shape

```json
{"type":"about:blank","title":"Meal completion conflict","status":409,"code":"conflict","detail":"Insufficient inventory for the requested consumption.","requestId":"uuid"}
```
