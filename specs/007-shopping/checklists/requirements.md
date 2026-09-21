# Shopping Checklist

- [ ] Generation reuses the 006 deterministic projection; only `shortfall > 0` lines become items.
- [ ] One non-archived list per household window; duplicate generation returns `409`.
- [ ] Purchase creates lot + `purchase` movement + item update in ONE transaction.
- [ ] Item `pending → purchased|skipped`, `skipped → pending`; list `open → completed` (zero pending), `completed → open`, terminal `archived`.
- [ ] `expected_version` on every mutation; operation idempotency receipts replay stored results.
- [ ] Composite tenant FKs; purchased lot MUST belong to the household.
- [ ] Plan mutation, consumption, unit conversion, email, notifications, and deployment are out of scope.
