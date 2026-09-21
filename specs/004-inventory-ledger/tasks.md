# Tasks: Inventory Ledger

- [ ] T001 [P] Complete analyze/checklist traceability in `specs/004-inventory-ledger/analyze.md`.
- [ ] T002 [P] Add pure Decimal ledger/no-negative/idempotency tests in `tests/unit/domain/test_inventory_ledger.py`.
- [ ] T003 Implement ledger value objects and movement policy in `src/uribap_api/domain/inventory/ledger.py`.
- [ ] T004 Add inventory lot/movement models and Alembic migration in `src/uribap_api/infrastructure/persistence/inventory_models.py` and `migrations/versions/`.
- [ ] T005 Add PostgreSQL locking/reconciliation/idempotency integration tests in `tests/integration/test_inventory_ledger.py`.
- [ ] T006 Implement inventory service/routes/schemas in `src/uribap_api/application/inventory_service.py`, `src/uribap_api/api/inventory.py`, and `src/uribap_api/api/inventory_schemas.py`.
- [ ] T007 Add API errors/OpenAPI coverage and update `openapi/openapi.json`.
- [ ] T008 Run full API testing skill gates and record evidence in `specs/004-inventory-ledger/quickstart.md`.
- [ ] T009 Write `specs/004-inventory-ledger/converge.md` and resolve remaining work.
