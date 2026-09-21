# Research: Ingredients, Units, and Recipes

## Quantity model

- **Decision**: Keep Decimal-safe string amounts and explicit dimensions (`count`, `mass`, `volume`) with base unit codes.
- **Rationale**: Existing foundation quantity contract already prevents floating-point and implicit density assumptions.
- **Rejected**: floats, free-form unit strings, and automatic mass/volume conversion.

## Versioning

- **Decision**: Recipe identity is stable; every edit creates a sequential version. Published versions are immutable.
- **Rationale**: Meal plans and future projections need historical recipe truth.
- **Rejected**: mutable recipe rows and snapshotting recipe JSON inside meal plans.

## Scope/search

- **Decision**: Global ingredients are read-only to households; household overrides are scoped by household. PostgreSQL normalized indexes are the initial search boundary.
- **Rationale**: Avoid a search service before scale requires it and preserve tenant authorization in one repository.
- **Rejected**: Elasticsearch/external catalog/media integration.

## Sources and constraints

- Existing API constitution and plan master define Decimal quantities, no images/nutrition in MVP, and API as the canonical domain boundary.
- UV remains the only Python dependency/environment workflow.
