# Plan: Shopping Projection and Purchases

Pure list/item state machines and version policy live in `domain/shopping/policies.py` without FastAPI/SQLAlchemy. Persistence adds `shopping_list`, `shopping_item`, and `shopping_operation` (idempotency receipts) with Alembic, reusing the 005 patterns (composite tenant FKs, partial unique index on the non-archived window). The application service generates items by reusing the 006 `forecast_service` projection, locks the list row (`SELECT FOR UPDATE`) for `expected_version`, and bridges purchases into `inventory_lot` + `purchase` `inventory_movement` inside the same transaction. Routes expose `/shopping-lists` CRUD, item `purchase`/`skip`/`restore`, and `complete`/`reopen`/`archive` transitions. Use UV only.

## Gates

Pure state-machine/version tests precede persistence; then PostgreSQL migration, concurrency/idempotency/tenant tests, purchase-transaction tests, OpenAPI export, security, Docker health, and resource checks.

## Model policy

- Primary architecture: `gpt-5-6-luna-max`.
- Implementation: `gpt-5-6-sol-high`.
- Reviewer: `gpt-5-6-terra-high` for the purchase transaction, idempotency, and tenant isolation.
- Analysis/subagent: `glm-5-3-max` for long artifact review.
- Bounded fixes: `swe-2-high`; escalate to `swe-2-max` only for a contained multi-file correction.
- Escalation condition: stop and request architectural review if the atomic purchase transaction, unique-window rule, or replay-without-duplicate-lot guarantee cannot be proven by tests.

## Delivery controls

- API checks: UV Ruff, Pyright, unit/API/integration tests, Alembic upgrade/check, OpenAPI export/check, pip-audit, Docker health/smoke, and resource sample.
- Database checks: version increments, composite tenant FKs, unique non-archived window, idempotency replay/conflict, item status CHECKs, and the purchase transaction (lot + movement + item update atomically).
- No email delivery or deployment is required for this feature; both remain explicit out of scope.

## Delivery impact summary

Per the constitution, each stacked PR declares its impact on migrations, contract, tests, security, and deployment:

| Layer | Migrations | Contract | Tests | Security | Deployment |
|-------|------------|----------|-------|----------|------------|
| spec | none | shopping contract doc | checklist/tasks | purchase transaction rule defined | none |
| domain | none | none | pure policy tests | item/list transition invariants | none |
| persistence | new revision adds 3 tables | none | PostgreSQL schema/integration tests | composite tenant FKs, unique window index | none |
| service | none | `/shopping-lists*` routes + Problem Details | API contract + replay/purchase tests | household scoping, optimistic concurrency, idempotency | none (deployment stays out of scope) |
