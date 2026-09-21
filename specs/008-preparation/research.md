# Research: Preparation

- Reuses `recipe_preparation_rule` + `PreparationRuleType` + `validate_lead_minutes`
  from phase 003; rules lacked an API until now.
- Follows the phase 005/007 receipt pattern (`*_operation` table, request hash,
  stored `result_payload`) and the shopping composite-FK tenancy model.
- Derivation-in-transaction avoids a scheduler and keeps plan approval atomic; the
  unique partial index makes concurrent approvals converge.
- `zoneinfo.ZoneInfo` resolves `household.timezone`; an invalid value falls back to
  UTC (documented, no crash).
- Fixed local meal start times keep `due_at` deterministic and reviewable without
  per-household configuration in this phase.
