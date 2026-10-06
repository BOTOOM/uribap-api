# Research: Pantry Staple Ingredients

## Decisions

1. **Store the flag on `ingredient`.** Pantry status is a household catalog property reused by every
   recipe, forecast, and meal completion. This requires one nullable-free Boolean column with a
   server default and does not introduce recipe-specific state.
2. **Do not remove staples from recipes or forecast demand.** Recipe display and required/optional/
   total demand remain authoritative; only completion consumption and staple shortfall semantics
   change.
3. **Treat any positive on-hand amount as stocked for staples.** Forecast shortfall is all demand
   only when on-hand equals zero. Plan detail uses the same zero-stock threshold for the row's
   required amount.
4. **Do not special-case shopping generation.** It already consumes positive forecast shortfalls,
   so the forecast projection is the single source of truth.
5. **Keep existing completion lifecycle behavior.** Staple lines are absent from new completions,
   so skip, correction, reopen, and reversal mechanisms need no new movement type or persistence.
6. **Keep global catalog rows read-only.** The existing update service's 403 is reused; no
   household-level override of a global ingredient is introduced.

## Alternatives not selected

- Removing pantry ingredients from recipe versions would lose their cooking instructions and
  demand visibility.
- Adding pantry status to recipe lines would allow inconsistent classification of the same
  household ingredient and complicate ingredient catalog editing.
- Treating partial staple stock as a proportional shortfall would conflict with the user's explicit
  “only when it runs out” requirement.
- Duplicating pantry rules in the shopping service or Web client would create multiple sources of
  truth.

## Dependencies and migration

No new package is required. The migration is additive and reversible and starts from the verified
single head `6b1354a22e91`.
