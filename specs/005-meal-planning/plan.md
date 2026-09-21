# Plan: Meal Planning and Collaboration

Pure plan state machine and version policy live in `domain/planning/policies.py` without FastAPI/SQLAlchemy. Persistence adds `meal_plan`, `meal_plan_entry`, `meal_plan_state_event`, and `meal_plan_operation` (idempotency receipts) with Alembic. The application service coordinates `SELECT FOR UPDATE` on the plan row, validates `expected_version`, and appends state events transactionally. Routes expose `/plans` CRUD plus `propose`/`approve`/`reopen`/`archive` transitions. Reuse 002 household authorization, 003 published recipe versions, and 004 idempotency/Problem Details patterns. Use UV only.

## Gates

Pure state-machine/version tests precede persistence; then PostgreSQL migration, concurrency/idempotency/tenant tests, OpenAPI export, security, Docker health, and resource checks.

## Model policy

- Primary architecture: `gpt-5-6-luna-max`.
- Implementation: `gpt-5-6-sol-high`.
- Reviewer: `gpt-5-6-terra-high` for transactions, concurrency, and security.
- Analysis/subagent: `glm-5-3-max` for long artifact review.
- Bounded fixes: `swe-2-high`; escalate to `swe-2-max` only for a contained multi-file correction.
- Escalation condition: stop and request architectural review if optimistic concurrency, approval rules, tenant isolation, or the no-inventory-mutation invariant cannot be proven by tests.

## Delivery controls

- API checks: UV Ruff, Pyright, unit/API/integration tests, Alembic upgrade/check, OpenAPI export/check, pip-audit, Docker health/smoke, and resource sample.
- Database checks: version increments, composite tenant foreign keys, append-only state events, idempotency replay/conflict, unique active plan per week, and concurrent mutation tests.
- No email delivery or deployment is required for this feature; both remain explicit out of scope.

## Delivery impact summary

Per the constitution, each stacked PR declares its impact on migrations, contract, tests, security, and deployment:

| Layer | Migrations | Contract | Tests | Security | Deployment |
|-------|------------|----------|-------|----------|------------|
| spec | none | meal-planning contract doc | checklist/tasks | approval-separation rule defined | none |
| domain | none | none | pure policy tests | approver != proposer invariant | none |
| persistence | `b5c9e1a3d407` adds 4 tables + append-only trigger | none | PostgreSQL schema/integration tests | composite tenant FKs, partial unique index | none |
| service | none | `/plans*` routes + `MealPlanEntryResponse` + Problem Details | API contract + replay/conflict tests | household scoping, optimistic concurrency, idempotency | none (deployment stays out of scope) |
