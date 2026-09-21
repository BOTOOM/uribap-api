# Meal Planning API Contract

Base path: `/api/v1`. Every route requires a bearer token, active membership, and `X-Household-ID` (UUID). JSON timestamps are UTC ISO-8601. Mutations accept `Idempotency-Key` (max 128) and require `expected_version` in the body where noted.

## `POST /plans`

Request: `{"week_start_date":"2026-09-28"}` (MUST be a Monday).

Response `201`: `MealPlanResponse` `{id, week_start_date, state:"draft", version:1, entries:[], created_at, updated_at}`. `409` when a non-archived plan already exists for the week; `422` invalid date.

## `GET /plans/current?week_start=2026-09-28` and `GET /plans/{plan_id}`

Response `200`: `MealPlanResponse` including `entries` ordered by `planned_date`, `position`, plus `state`/`version`. `404` unknown plan; `403` cross-household.

## `POST /plans/{plan_id}/entries`

Headers: `Idempotency-Key` optional. Request:

```json
{"expected_version":1,"planned_date":"2026-09-29","meal_type":"dinner","recipe_version_id":"uuid","servings":2,"position":0,"notes":null}
```

Response `201`: `MealPlanResponse` — the authoritative plan snapshot including the bumped `version` and `entries`, so clients can chain `expected_version` without a second fetch. `409` on version mismatch, non-draft plan, duplicate `(planned_date, meal_type)` position conflict, or idempotency hash mismatch; `422` unpublished recipe version / invalid servings / date outside week.

## `PATCH /plans/{plan_id}/entries/{entry_id}` and `DELETE /plans/{plan_id}/entries/{entry_id}`

Both require `expected_version` and return `MealPlanResponse` (same deliberate snapshot contract as entry creation); same `409`/`422` semantics. `PATCH` accepts `planned_date`, `meal_type`, `recipe_version_id`, `servings`, `position`, `notes`; a changed `recipe_version_id` MUST still reference a `published` version of the household (`422` otherwise), and an explicit `notes: null` clears the note. `DELETE` removes the entry and bumps the version.

## `POST /plans/{plan_id}/propose`, `/approve`, `/reopen`, `/archive`

Request: `{"expected_version":N,"note":null}`. Each appends a `meal_plan_state_event` and bumps the version.

- `propose`: `draft → proposed`.
- `approve`: `proposed → approved`; with ≥2 active members the approver MUST differ from the proposer (`409` otherwise).
- `reopen`: `proposed → draft` (or `approved → draft` with note required).
- `archive`: `draft|proposed|approved → archived`.

`409` on illegal transition or version mismatch; `422` on missing note where required.

## `GET /plans/{plan_id}/events`

Response `200`: `{ "items": [MealPlanStateEventResponse] }` oldest-first; append-only audit.

## Error shape

```json
{"type":"https://uribap.app/problems/conflict","title":"Plan version conflict","status":409,"code":"conflict","detail":"The plan changed since you loaded it.","request_id":"uuid"}
```
