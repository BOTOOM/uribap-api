# Feature Specification: Ingredients, Units, and Recipes

**Feature Branch**: `003-ingredients-units-recipes`
**Created**: 2026-09-21
**Status**: Ready for implementation

## User Scenarios & Testing

### User Story 1 - Manage household ingredients and units (Priority: P1)

As a household member, I want a canonical ingredient catalog with safe units so that inventory and recipes refer to the same quantities without dimensional guesses.

**Independent Test**: An authorized member creates/reads/updates an ingredient, rejects invalid dimensions/units, and confirms a second household cannot access it.

**Acceptance Scenarios**:

1. **Given** an authorized owner/admin, **When** an ingredient is created with a name, dimension, base unit, and optional pack size, **Then** the API normalizes the name and returns a stable ingredient resource.
2. **Given** an ingredient with dimension `mass`, **When** a quantity uses `g` or `kg`, **Then** it is accepted and normalized; `ml` or `l` is rejected without conversion assumptions.
3. **Given** a global ingredient, **When** a household reads the catalog, **Then** it can use the global record without mutating it.
4. **Given** a household ingredient, **When** another household requests it, **Then** the API returns safe tenant denial.

### User Story 2 - Create versioned recipes (Priority: P1)

As a household member, I want recipes with immutable versions, ingredients, instructions, meal types, and preparation rules so that future planning can reference a reproducible recipe version.

**Independent Test**: A member creates a recipe draft, adds ingredients/instructions, publishes version 1, edits it into version 2, and verifies version 1 remains unchanged.

**Acceptance Scenarios**:

1. **Given** a member, **When** a recipe draft is created, **Then** the API returns a stable recipe identity and draft version.
2. **Given** a draft version, **When** recipe ingredients use compatible units and positive quantities, **Then** the version can be saved; incompatible units or zero quantities are rejected.
3. **Given** a published version, **When** the recipe is edited, **Then** a new version is created and the published historical version remains readable.
4. **Given** a recipe version, **When** meal types, instructions, tags, and preparation rules are added, **Then** the API preserves ordering and validates lead times.

### User Story 3 - Discover and favorite recipes (Priority: P2)

As a household member, I want to search, filter, favorite, archive, and read recipes so that meal planning can select known versions quickly.

**Independent Test**: A member searches recipes by normalized name/tag/meal type, favorites one recipe, archives another, and confirms archived data is excluded from active results but remains readable by authorized users.

**Acceptance Scenarios**:

1. **Given** active recipes in the household/global catalog, **When** a member searches with a term and meal type, **Then** results are scoped, paginated, and stable.
2. **Given** a recipe, **When** a member favorites/unfavorites it, **Then** the operation is idempotent per user/recipe.
3. **Given** an archived recipe, **When** active search runs, **Then** it is excluded unless the caller requests archived records.

### Edge Cases

- Duplicate normalized ingredient names in the same household.
- A global ingredient name collides with a household override.
- Quantity dimensions differ even when units look numerically convertible.
- A recipe version references an archived ingredient.
- Concurrent version publication or edits.
- A recipe has no instructions, no meal type, or an invalid preparation lead time.
- A favorite is repeated or removed after the recipe is archived.
- A household member loses membership between read and mutation.

## Requirements

- **FR-001**: The API MUST represent ingredient dimension separately from unit code and MUST reject cross-dimension quantities.
- **FR-002**: Ingredient names MUST be normalized for uniqueness within global/household scope while retaining a display name.
- **FR-003**: Supported MVP units MUST remain `unit`, `g`, `kg`, `ml`, and `l`; no density or cross-dimension conversion is allowed.
- **FR-004**: Ingredient quantities MUST use Decimal/NUMERIC-safe string amounts and MUST be positive where recipe demand is defined.
- **FR-005**: Ingredients MUST support global scope and household scope with tenant authorization.
- **FR-006**: Recipes MUST have stable identity and immutable, sequential versions with draft/published/archived states.
- **FR-007**: Recipe versions MUST support ordered ingredient lines, ordered instructions, meal types, tags, and preparation rules.
- **FR-008**: A published recipe version MUST NOT be mutated in place.
- **FR-009**: Search/list endpoints MUST support pagination, normalized search, meal-type/tag filters, and archived filtering.
- **FR-010**: Favorites MUST be idempotent per user and recipe.
- **FR-011**: All household-owned ingredients/recipes MUST require active household membership.
- **FR-012**: All mutations MUST expose Problem Details, correlation ID, and optimistic/idempotency behavior where applicable.
- **FR-013**: API contracts MUST be exported into the canonical OpenAPI snapshot for Web generation.
- **FR-014**: No image, nutrition, marketplace, or email delivery functionality is part of this feature.

## Key Entities

- **Ingredient**: scoped canonical food/product concept with dimension, base unit, pack size, and normalization metadata.
- **Recipe**: stable household recipe identity and archive state.
- **RecipeVersion**: immutable revision with servings, prep time, state, and publication metadata.
- **RecipeVersionIngredient**: ordered ingredient quantity and optionality.
- **RecipeInstruction**: ordered preparation text.
- **RecipeMealType**: breakfast/lunch/dinner/snack association.
- **RecipeTag / RecipeTagLink**: reusable labels and recipe associations.
- **RecipeFavorite**: user/recipe idempotent favorite.
- **RecipePreparationRule**: defrost/soak/marinate/prepare-ahead lead-time rule.

## Success Criteria

- **SC-001**: 100% of incompatible unit/dimension tests are rejected without implicit conversion.
- **SC-002**: Concurrent duplicate ingredient creation leaves one normalized household record.
- **SC-003**: Published recipe version content is immutable and version 2 preserves version 1 history.
- **SC-004**: 100% of cross-household ingredient/recipe access tests return safe denial.
- **SC-005**: Search returns active authorized recipes with stable pagination and filters.
- **SC-006**: OpenAPI export and generated Web client checks pass deterministically.
- **SC-007**: Pure quantity/version/favorite policy tests run without FastAPI/PostgreSQL.

## Assumptions

- Household/global ingredient records are enough for the MVP; no third-party ingredient database is integrated.
- Recipe quantities use the same supported dimensions as foundation.
- Nutrition and media remain separate future features.
- All code and tests use UV in API and pnpm in Web; no email delivery or deployment is required for this phase.
