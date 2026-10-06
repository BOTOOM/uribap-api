# Data Model: Pantry Staple Ingredients

## Ingredient

Add the following persisted attribute to the existing `ingredient` entity:

| Field | Type | Nullability | Default | Meaning |
|---|---|---|---|---|
| `pantry_staple` | Boolean | not null | server default `false` | Ingredient remains in recipes and demand but is not consumed when a meal is cooked. |

### Invariants

- A migration adds the column after the current revision `6b1354a22e91`.
- Existing rows receive `false`; new REST/MCP create requests also default to `false`.
- Update requests may omit the field; when present, `true` or `false` replaces its value.
- Global catalog ingredients cannot be changed by a household member.
- Pantry status belongs to the ingredient, so every recipe use of the same ingredient has the same
  behavior.

## Recipe demand and completion

- Recipe-version ingredient rows are unchanged; staple ingredients remain ordinary recipe lines.
- Forecast demand retains the required, optional, and total amount calculations for every line.
- Completion consumption lines include only non-staple ingredients. A recipe with all staple lines
  produces zero completion lines; a recipe with no ingredient rows keeps the existing validation
  error.
- An explicit completion payload line for a staple is invalid and returns the specified 422 detail.

## Read projections

- Forecast lines add `pantry_staple`. For staples, shortfall is total demand when `on_hand_amount`
  is zero and zero otherwise.
- Plan-entry detail ingredient rows add `pantry_staple`. For staples, shortfall is required amount
  when on-hand is zero and zero otherwise; staple rows do not decrement shared `remaining_stock`.
- Non-staple shortfall and stock-allocation behavior remain unchanged.
