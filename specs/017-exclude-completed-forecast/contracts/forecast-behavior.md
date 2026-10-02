# Forecast Behavior Contract

The endpoint and response shape are unchanged; the canonical forecast query semantics change.

## Corrected semantic rule

`GET /api/v1/forecast/demand` and `uribap_get_forecast` project demand from approved plan entries in
the requested date window only when the entry does not have a household-scoped completion in the
`recorded` state. Completion outcome does not affect this rule.

- Recorded cooked completion: entry demand is excluded.
- Recorded skipped completion: entry demand is excluded.
- Reopened completion: entry demand is included.
- Approved plan identifiers remain in `considered_plan_ids`.
- Shopping-list generation receives the same corrected semantics through the forecast service.

The rule is implemented with a correlated `NOT EXISTS` matching both household and plan-entry id.
