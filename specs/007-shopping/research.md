# Research: Shopping Projection and Purchases

- List-per-window with a partial unique index mirrors the 005 active-week rule: regenerating a live window conflicts instead of silently diffing; a new window or archiving the old list is the explicit path.
- Shortfall-only items keep the list actionable; covered lines stay visible in the 006 projection but are not purchasable work.
- Purchase = lot + `purchase` movement in one transaction reuses the 004 ledger path with `source_type="shopping_item"`/`source_id` for traceability; bought quantity MAY exceed the shortfall (bulk packages) without domain complaints.
- `skipped` captures "won't buy" so `complete` can require zero pending while still allowing a restore path; `purchased` is terminal for the item.
- One receipt table `shopping_operation` generalizes the 004/005 idempotency pattern to list generation, item ops, and transitions, storing `result_payload` for original-result replay — critical so a replayed purchase cannot mint a duplicate lot.
- Optimistic `version` + `SELECT FOR UPDATE` matches plans: Web sends `expected_version` from server-loaded state.
