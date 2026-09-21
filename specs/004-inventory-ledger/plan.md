# Plan: Inventory Ledger

Use SQLAlchemy/Alembic/PostgreSQL with Decimal NUMERIC values. Keep ledger rules in pure `domain/inventory/ledger.py`; lock lots with `SELECT FOR UPDATE` inside the service transaction. Reuse 002 household authorization and 003 ingredient dimensions. Expose `/inventory`, `/inventory/lots`, and `/inventory/adjustments`. Use UV only.

## Gates

Pure ledger tests precede persistence; then PostgreSQL migration, concurrent/no-negative/idempotency tests, OpenAPI export, security, Docker health, and resource checks.

## Model policy

Luna architecture, Sol implementation, Terra concurrency/security review, SWE-2 quality fixes.
