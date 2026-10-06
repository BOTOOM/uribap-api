# Forecast Pantry-Staple Contract

Forecast demand remains unchanged for each ingredient:

- `required_amount`, `optional_amount`, and `total_amount` are calculated as before.
- The response line adds `pantry_staple: bool`.
- For a pantry staple, `shortfall_amount` equals `total_amount` if `on_hand_amount == 0`, and equals
  zero otherwise.
- For a non-staple, `shortfall_amount = max(total_amount - on_hand_amount, 0)` remains unchanged.
- Shopping-list generation remains unchanged and continues to include positive shortfalls.
