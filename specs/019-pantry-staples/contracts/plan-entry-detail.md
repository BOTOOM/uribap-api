# Plan-Entry Detail Pantry-Staple Contract

Each ingredient row adds `pantry_staple: bool`.

- A pantry staple's `shortfall_amount` is `required_amount` when on-hand is zero, and zero
  otherwise.
- A pantry-staple row does not reduce shared `remaining_stock`, so it cannot reserve stock from
  subsequent recipe rows.
- Existing non-staple allocation, ordering, expiry, scaling, and response behavior are unchanged.
