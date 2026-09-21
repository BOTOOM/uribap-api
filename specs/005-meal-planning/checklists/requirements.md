# Meal Planning Checklist

- [x] Optimistic `version` + `expected_version` semantics are explicit.
- [x] State machine, editable states, and approval rule (approver != proposer when ≥2 members) are explicit.
- [x] Append-only state events and operation-scoped idempotency are required.
- [x] Entries pin published recipe versions; planning never mutates inventory.
- [x] Email, notifications, deployment, forecasting, shopping, and completion are out of scope.
