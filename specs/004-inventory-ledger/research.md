# Research: Inventory Ledger

- PostgreSQL `NUMERIC(18,6)` maps to Python Decimal and avoids floating-point drift.
- Cached balance plus append-only movement history is required for fast reads and reconstruction.
- `SELECT FOR UPDATE` on the lot row is the transaction boundary for no-negative concurrent mutations.
- Idempotency keys are scoped to household/operation and store a safe response fingerprint.
