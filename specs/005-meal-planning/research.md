# Research: Meal Planning and Collaboration

- Optimistic concurrency via an integer `version` column plus `expected_version` in requests is simpler and auditable; `SELECT ... FOR UPDATE` on the plan row serializes writers inside the transaction.
- Approval semantics for households: with one active member self-approval is unavoidable; with two or more, requiring approver != proposer makes collaboration meaningful and deterministic.
- Pinning `recipe_version_id` (published only) preserves the plan even when the recipe evolves, matching the recipe-versioning decision from 003.
- A single `meal_plan_operation` receipt table generalizes the inventory idempotency pattern to all plan mutations (entry create/update/delete and transitions) while keeping `result_payload` for original-result replay.
- Append-only `meal_plan_state_event` mirrors `inventory_movement` protections: corrections are new transitions, never edits.
- Planning is projected demand; forecasting reads plans later. Keeping mutations inventory-free preserves constitution principle I.
