# Meal Completion Outcome Contract

## Skip a plan entry

`POST /api/v1/plans/{plan_id}/entries/{entry_id}/skip`

- Authentication and active household membership are required.
- Request body: `MealCompletionSkip` with `reason: string | null`, maximum 2000 characters.
- `Idempotency-Key` is optional, limited to 128 characters, and uses the same completion receipt
  and request-fingerprint behavior as `/complete`.
- Receipt operation name: `meal_entry_skip`.
- Success: `201 Created`, response `MealCompletionResponse`.
- The plan must exist in the household and be approved; otherwise return the existing `404` or `409`
  domain error.
- The entry must belong to that plan and household; otherwise return `404`.
- An already recorded completion returns `409` with the existing recorded-completion conflict.

A successful response has `state: "recorded"`, `outcome: "skipped"`,
`outcome_note` equal to the submitted reason, and `lines: []`. The operation does not create
inventory movements or change lot balances. It records `MEAL_COMPLETED` with payload:

```json
{
  "meal_plan_entry_id": "<entry UUID>",
  "line_count": 0,
  "outcome": "skipped"
}
```

## Completion response

`MealCompletionResponse` adds:

- `outcome`: `"cooked" | "skipped"`
- `outcome_note`: string or `null`

Existing completions are backfilled as cooked. Reopened skipped completions keep their skipped
outcome and note but no longer suppress forecast demand. Cooked completion events include
`"outcome": "cooked"`.

## MCP tools

- `uribap_skip_meal(plan_id, entry_id, reason=None, idempotency_key=None)` is a WRITE tool with
  title `"Mark meal as not cooked"` and description:
  `"Record that a planned meal was not cooked at home (delivery, ate out, skipped). Removes it from forecast and shopping demand without touching inventory. Reopen the completion to undo."`
- `uribap_complete_meal` describes that cooked meals also leave forecast and shopping demand.
