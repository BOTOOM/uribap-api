# Implementation Plan: Ingredients, Units, and Recipes

**Branch**: `003-ingredients-units-recipes` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

## Summary

Add the canonical ingredient/unit and versioned recipe domain to the modular FastAPI monolith. Pure quantity/dimension/version policies will be implemented before SQL/API integration. PostgreSQL persistence will use a reviewed Alembic migration, Decimal-safe string schemas, household authorization dependencies from 002, and OpenAPI-first routes for Web.

## Technical Context

**Language/Version**: Python 3.14
**Primary Dependencies**: Existing FastAPI, SQLAlchemy 2, Alembic, Pydantic, PyJWT/httpx identity boundary
**Python Tooling**: UV exclusively (`uv sync --locked`, `uv run`), committed `uv.lock`
**Storage**: PostgreSQL 18 application database
**Testing**: UV Ruff, Pyright, pytest unit/API/integration, PostgreSQL constraints, OpenAPI snapshot
**Constraints**: Decimal quantities, no cross-dimension conversion, immutable published versions, tenant isolation, no media/nutrition/email/deployment
**Scale/Scope**: Household/global ingredient catalog and practical recipe volume for MVP homes

## Constitution Check

- Domain correctness: PASS; quantity policies are pure and explicit.
- Determinism/test-first: PASS; unit conversion/normalization/version state precede routes.
- Tenant isolation: PASS; household records reuse membership dependency and scope filters.
- Contract-first: PASS; all resources are in OpenAPI and generated Web client.
- Auditable operations: PASS; recipe versions are historical and mutations carry request IDs/version conflicts.
- Resource-aware simplicity: PASS; no search service or queue; PostgreSQL indexes/pg_trgm only if justified by measured need.

## Model Assignment

- Primary: `gpt-5-6-luna-high`
- Implementation: `gpt-5-6-sol-high`
- Reviewer: `gpt-5-6-terra-high`
- Artifact analyst: `glm-5-3-max`
- Routine fixer: `swe-2-high`; broader bounded fixes `swe-2-max`

## Project Structure

```text
specs/003-ingredients-units-recipes/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/ingredients-recipes.md
├── traceability.md
├── quickstart.md
├── analyze.md
├── converge.md
└── tasks.md

src/uribap_api/
├── domain/ingredients/
├── domain/recipes/
├── infrastructure/persistence/ingredient_models.py
├── infrastructure/persistence/recipe_models.py
├── application/ingredient_service.py
├── application/recipe_service.py
└── api/ingredients.py, api/recipes.py

migrations/versions/<ingredients-recipes>.py
tests/unit/domain/test_quantities.py
tests/unit/domain/test_recipe_versions.py
tests/api/test_ingredient_routes.py
tests/api/test_recipe_routes.py
tests/integration/test_recipe_isolation.py
```

## Phases

1. Spec/research/model/contracts/tasks/analyze.
2. Pure quantity, normalization, recipe-state, version, and favorite policies.
3. PostgreSQL models/migration/indexes.
4. Ingredient API and tests.
5. Recipe/version API and tests.
6. OpenAPI/Web client sync and full UV/API gates.
7. Convergence and stacked PR merge.
