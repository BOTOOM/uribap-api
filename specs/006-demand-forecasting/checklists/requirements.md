# Demand Forecasting Checklist

- [x] Only `approved` plan entries inside the window feed the projection.
- [x] `Decimal` serving scaling and per-`(ingredient, unit)` aggregation are explicit; no unit conversion.
- [x] Required/optional split, on-hand rule (available, positive, unexpired at `from_date`), and `max(0, total - on_hand)` shortfall are explicit.
- [x] The endpoint is read-only and deterministic; no new tables, no volatile fields.
- [x] Window defaults, `from <= to`, and the 62-day cap are explicit.
- [x] Shopping, purchases, preparation, consumption, email, notifications, and deployment are out of scope.
