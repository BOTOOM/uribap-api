# Tasks: Shopping

- [ ] T001 [P] Complete analyze/checklist traceability in `specs/007-shopping/analyze.md` and `traceability.md`.
- [ ] T002 [P] Add pure state-machine/version/purchase-validation tests in `tests/unit/domain/test_shopping_policies.py`.
- [ ] T003 Implement shopping policies in `src/uribap_api/domain/shopping/policies.py`.
- [ ] T004 Add list/item/operation models and Alembic migration in `src/uribap_api/infrastructure/persistence/shopping_models.py` and `migrations/versions/`.
- [ ] T005 Add PostgreSQL schema/idempotency/tenant integration tests in `tests/integration/test_shopping_schema.py`.
- [ ] T006 Implement shopping service/routes/schemas in `src/uribap_api/application/shopping_service.py`, `src/uribap_api/api/shopping.py`, and `src/uribap_api/api/shopping_schemas.py`.
- [ ] T007 Add service integration tests: generation from projection, atomic purchase, replay, conflicts in `tests/integration/test_shopping_service.py` plus API route contract coverage.
- [ ] T008 Update `openapi/openapi.json` and the shopping contract doc.
- [ ] T009 Run full API testing skill gates and record evidence in `specs/007-shopping/quickstart.md`.
- [ ] T010 Write `specs/007-shopping/converge.md` and track remaining work.
