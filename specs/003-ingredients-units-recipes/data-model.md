# Data Model: Ingredients, Units, and Recipes

## Ingredient

- UUID, nullable household owner for global records, display name, normalized name, category, dimension, base unit, optional package size, archived timestamp.
- Unique normalized name within `(household_id, normalized_name)`; global records use a separate global scope.
- `dimension` controls allowed units and is never inferred from names.

## Recipe

- UUID, household owner, name, description, creator, archived timestamp.
- Unique active name per household is not required; normalized search is indexed.

## RecipeVersion

- UUID, recipe ID, sequential version number, base servings > 0, prep minutes >= 0, state `draft/published/archived`, created/published by, timestamps.
- Unique `(recipe_id, version_number)`.
- Published rows are immutable; editing creates next version.

## RecipeVersionIngredient

- Version ID, ingredient ID, Decimal amount string/NUMERIC equivalent, unit, display order, optional boolean.
- Foreign keys are restricted where historical recipe versions exist.

## RecipeInstruction

- Version ID, position, text; unique `(version_id, position)`.

## RecipeMealType

- Version ID and meal type enum `breakfast/lunch/dinner/snack`; unique pair.

## RecipeTag / RecipeTagLink

- Household/global normalized tag and version/recipe association.

## RecipeFavorite

- User ID, recipe ID, created timestamp; unique `(user_id, recipe_id)`.

## RecipePreparationRule

- Version ID, type `defrost/soak/marinate/prepare_ahead`, optional ingredient ID, lead minutes >= 0, instruction.

## Invariants

- Every household-owned query requires active membership.
- Recipe quantities must match ingredient dimension.
- Published version cannot be mutated.
- Archived recipe/ingredient remains readable only through explicit archived query.
