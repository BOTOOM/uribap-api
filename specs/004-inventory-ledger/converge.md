# Convergence: Inventory Ledger

**Status**: Implementation complete pending clean-database integration evidence.

## Implemented

- Decimal finite/scale/range policy and deterministic operation fingerprints.
- Inventory lot/movement models and Alembic schema with composite tenant FK, idempotency metadata, partial index, and append-only trigger.
- Row-locked adjustments, no-negative balance, operation-scoped idempotency replay/conflict, expired-lot filtering, bounded input validation, and Problem Details/OpenAPI responses.
- Unit/API/schema tests, generated OpenAPI, and Web contract/UI consumers.

## Evidence

- Local static/domain/API gates: PASS.
- Local unit/API tests: 38 passed, 2 warnings.
- Local pip-audit: PASS.
- Local integration schema test: NOT PASS because the development database already contains the pre-hardening f4 schema and was not downgraded or dropped. CI starts a fresh PostgreSQL service and applies the current head migration before running the complete suite.

## Remaining gates

- Confirm GitHub API quality on a clean PostgreSQL service.
- If green, mark T005/T008/T009 complete and merge the native stack.
- No email delivery or deployment is required for this feature.
