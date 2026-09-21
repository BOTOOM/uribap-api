# Research: Deterministic Demand Forecasting

- Approved-only source: `approved` is the confirmed active state from 005; `draft`/`proposed` are intent under review, and `archived` is terminal history. This keeps projected demand stable while members edit drafts.
- Scaling: `servings / base_servings` as `Decimal` (six places, `ROUND_HALF_UP`) reuses the 004 quantization rule; scaling happens per entry before summing so partial-recipe factors cannot accumulate float error.
- Per-unit lines instead of conversion: no conversion table exists, and inventing densities would be non-deterministic product guessing; mismatched units surface as separate shortfalls, which is honest input for shopping in 007.
- Availability rule: lots expiring before `from_date` are excluded because they cannot serve any consumption inside the window; availability is evaluated at the window start, not per day, keeping the rule simple and deterministic.
- Read-only computation: storing snapshots adds write paths with no consumer yet (shopping lands in 007); determinism makes recomputation equivalent to a snapshot for identical inputs.
- Window cap of 62 days bounds the join without harming the weekly planning cadence.
