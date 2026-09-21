# Tasks: Ingredients, Units, and Recipes

**Model policy**: Luna architecture, Sol implementation, Terra review, GLM analysis, SWE-2 bounded fixes.

## Phase 1: Spec and pure domain

- [ ] T001 [P] Complete `analyze.md` and validate FR/SC traceability in `specs/003-ingredients-units-recipes/analyze.md`.
- [ ] T002 [P] Add dimension/unit compatibility and Decimal normalization tests in `tests/unit/domain/test_quantities.py`.
- [ ] T003 [P] Add ingredient normalization, recipe version, publish immutability, and favorite policy tests in `tests/unit/domain/test_recipe_versions.py`.
- [ ] T004 Implement pure ingredient/unit/version policies in `src/uribap_api/domain/ingredients/policies.py` and `src/uribap_api/domain/recipes/policies.py`.

## Phase 2: Persistence

- [ ] T005 Add SQLAlchemy ingredient/recipe models and relationships in `src/uribap_api/infrastructure/persistence/ingredient_models.py` and `recipe_models.py`.
- [ ] T006 Add reviewed Alembic migration/indexes/checks in `migrations/versions/`.
- [ ] T007 Add PostgreSQL integration tests for unique normalization, immutable published versions, tenant isolation, and favorite idempotency in `tests/integration/test_recipe_isolation.py`.

## Phase 3: Ingredients API

- [ ] T008 [P] Add ingredient API contract/error tests in `tests/api/test_ingredient_routes.py`.
- [ ] T009 Implement ingredient schemas/service/routes in `src/uribap_api/api/ingredients.py`, `src/uribap_api/application/ingredient_service.py`, and `src/uribap_api/api/schemas.py`.
- [ ] T010 Add OpenAPI export/snapshot coverage for ingredient resources in `tests/api/test_ingredient_openapi.py`.

## Phase 4: Recipes API

- [ ] T011 [P] Add recipe/version API contract tests in `tests/api/test_recipe_routes.py`.
- [ ] T012 Implement recipe/version/instruction/tag/favorite/preparation services in `src/uribap_api/application/recipe_service.py` and domain modules.
- [ ] T013 Implement recipe routes and schemas in `src/uribap_api/api/recipes.py` and `src/uribap_api/api/schemas.py`.
- [ ] T014 Add immutable publish/edit/concurrency integration tests in `tests/integration/test_recipe_versions.py`.
- [ ] T015 Export the API snapshot and sync Web contract after API routes stabilize in `openapi/openapi.json`.

## Phase 5: Verification and convergence

- [ ] T016 Run UV API gates, PostgreSQL migration, OpenAPI, audit, Docker smoke, and record evidence in `specs/003-ingredients-units-recipes/quickstart.md`.
- [ ] T017 Write `specs/003-ingredients-units-recipes/converge.md`, resolve remaining tasks, and mark the feature complete only after all checks pass.

## Dependencies

T001–T004 → T005–T007 → T008–T010 and T011–T015 → T016–T017.
