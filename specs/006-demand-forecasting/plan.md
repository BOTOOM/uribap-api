# Plan: Deterministic Demand Forecasting

Pure projection math lives in `domain/forecast/policies.py` without FastAPI/SQLAlchemy: serving scaling, `(ingredient, unit)` aggregation, and shortfall vs on-hand. No new tables — the projection is computed on read. The application service loads `approved` plans overlapping the window, their entries inside the window, the pinned recipe-version ingredients, and the available non-expired lots; then maps domain lines to a deterministic response. Routes expose `GET /forecast/demand`. Reuse 002 household authorization, 003 recipe version ingredients, 004 lot availability/Decimal rules, and 005 approved-plan semantics. Use UV only.

## Gates

Pure scaling/aggregation/shortfall tests precede the service; then API contract tests (window defaults, validation, deterministic payload), OpenAPI export, security, Docker health, and resource checks.

## Model policy

- Primary architecture: `gpt-5-6-luna-max`.
- Implementation: `gpt-5-6-sol-high`.
- Reviewer: `gpt-5-6-terra-high` for read-only guarantees, tenant isolation, and Decimal determinism.
- Analysis/subagent: `glm-5-3-max` for long artifact review.
- Bounded fixes: `swe-2-high`; escalate to `swe-2-max` only for a contained multi-file correction.
- Escalation condition: stop and request architectural review if the approved-only source, per-unit aggregation, or read-only guarantee cannot be proven by tests.

## Delivery controls

- API checks: UV Ruff, Pyright, unit/API/integration tests, OpenAPI export/check, pip-audit, Docker health/smoke, and resource sample.
- Database checks: none — no new tables; integration tests verify reads against existing schema.
- No email delivery or deployment is required for this feature; both remain explicit out of scope.

## Delivery impact summary

Per the constitution, each stacked PR declares its impact on migrations, contract, tests, security, and deployment:

| Layer | Migrations | Contract | Tests | Security | Deployment |
|-------|------------|----------|-------|----------|------------|
| spec | none | forecast contract doc | checklist/tasks | approved-only rule defined | none |
| domain | none | none | pure policy tests | Decimal determinism, no cross-unit merge | none |
| service | none | `GET /forecast/demand` + Problem Details | API contract + determinism tests | household scoping, read-only guarantee | none (deployment stays out of scope) |
