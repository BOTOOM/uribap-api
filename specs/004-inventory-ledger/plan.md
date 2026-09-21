# Plan: Inventory Ledger

Use SQLAlchemy/Alembic/PostgreSQL with Decimal NUMERIC values. Keep ledger rules in pure `domain/inventory/ledger.py`; lock lots with `SELECT FOR UPDATE` inside the service transaction. Reuse 002 household authorization and 003 ingredient dimensions. Expose `/inventory`, `/inventory/lots`, and `/inventory/adjustments`. Use UV only.

## Gates

Pure ledger tests precede persistence; then PostgreSQL migration, concurrent/no-negative/idempotency tests, OpenAPI export, security, Docker health, and resource checks.

## Model policy

- Primary architecture: `gpt-5-6-luna-max`.
- Implementation: `gpt-5-6-sol-high`.
- Reviewer: `gpt-5-6-terra-high` for transactions, concurrency, and security.
- Analysis/subagent: `glm-5-3-max` for long artifact review.
- Bounded fixes: `swe-2-high`; escalate to `swe-2-max` only for a contained multi-file correction.
- Escalation condition: stop and request architectural review if locking, idempotency, tenant isolation, or no-negative invariants cannot be proven by tests.

## Delivery controls

- API checks: UV Ruff, Pyright, unit/API/integration tests, Alembic upgrade/check, OpenAPI export/check, pip-audit, Docker health/smoke, and resource sample.
- Database checks: Decimal scale/range, composite tenant foreign keys, append-only movement protections, idempotency replay/conflict, and concurrent adjustment tests.
- No email delivery or deployment is required for this feature; both remain explicit out of scope.
