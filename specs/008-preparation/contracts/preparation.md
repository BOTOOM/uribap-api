# Preparation API Contract

Base path: `/api/v1`. Every route requires a bearer token, active membership, and
`X-Household-ID` (UUID). Mutations accept `Idempotency-Key` (max 128) and require
`expected_version` on existing tasks.

## `GET /preparation-tasks`

Query: `status` (`pending`/`completed`/`cancelled`), `from`, `to` (ISO datetimes
filtering `due_at`). Response `200`: `PreparationTaskPage` `{items:[PreparationTaskResponse]}`
ordered by `due_at, id`.

`PreparationTaskResponse` `{id, origin, task_type, title, instruction, due_at, status,
version, meal_plan_entry_id, planned_date, meal_type, recipe_version_id, recipe_name,
ingredient_id, ingredient_name, amount, unit, completed_by_user_id, completed_at,
created_at, updated_at}`.

## `POST /preparation-tasks`

Request: `{title, instruction?, due_at, ingredient_id?, amount?, unit?}` — creates a
`manual` task; `amount`/`unit` MUST be provided together. Response `201`:
`PreparationTaskResponse`. `404`/`403` unknown or cross-household ingredient; `422`
invalid payload.

## `POST /preparation-tasks/{task_id}/complete` and `/cancel`

Request: `{"expected_version":N}`. `pending → completed` records the actor and
timestamp; `pending → cancelled`. Response `200`: `PreparationTaskResponse`. `409`
illegal transition or version mismatch; `404` unknown task.

## `POST /recipes/{recipe_id}/versions/{version_id}/preparation-rules`

Request: `{rule_type, ingredient_id?, lead_minutes, instruction}` — draft versions
only (`422` otherwise). Response `201`: `PreparationRuleResponse` `{id,
recipe_version_id, rule_type, ingredient_id, ingredient_name, lead_minutes,
instruction}`.

## `DELETE /recipes/{recipe_id}/versions/{version_id}/preparation-rules/{rule_id}`

Draft versions only. Response `204`. `404` unknown rule; `422` non-draft version.

## Derivation behavior

`POST /plans/{plan_id}/approve` derives tasks atomically with the transition:
one `pending` task per plan entry × preparation rule of the entry's published recipe
version, `due_at = meal_start(planned_date, meal_type, household.timezone) -
lead_minutes` (breakfast 08:00, lunch 13:00, snack 17:00, dinner 20:00 local; invalid
timezone falls back to UTC). Re-approval inserts only missing fingerprints and
cancels `pending` derived tasks whose fingerprint is no longer produced.

## Error shape

```json
{"type":"about:blank","title":"Preparation task conflict","status":409,"code":"conflict","detail":"The task changed since you loaded it.","requestId":"uuid"}
```
