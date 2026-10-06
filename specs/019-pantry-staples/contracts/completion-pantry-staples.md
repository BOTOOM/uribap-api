# Completion Pantry-Staple Contract

- Completion planning excludes pantry staples from consumption lines before FEFO allocation.
- No pantry staple can be persisted as a completion line or create a completion inventory movement.
- A recipe version with zero ingredient rows returns the existing
  `the recipe version has no consumable ingredients` validation error.
- A recipe version with one or more ingredient rows, all marked as pantry staples, completes
  successfully with zero lines and no movements.
- An explicit payload line for a pantry staple returns status 422, code `validation_error`, and
  exact detail:
  `pantry staple ingredients are not consumed by completions; adjust the lot instead`
- Skip/delivery, correction, and reopen operations are unchanged.
