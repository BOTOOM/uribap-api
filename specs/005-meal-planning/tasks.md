# Tasks: Meal Planning

- [x] T001 [P] Complete analyze/checklist traceability in `specs/005-meal-planning/analyze.md` and `traceability.md`.
- [x] T002 [P] Add pure state-machine/version/idempotency tests in `tests/unit/domain/test_planning_policies.py`.
- [x] T003 Implement plan policies in `src/uribap_api/domain/planning/policies.py`.
- [x] T004 Add plan/entry/state-event/operation models and Alembic migration in `src/uribap_api/infrastructure/persistence/planning_models.py` and `migrations/versions/`.
- [x] T005 Add PostgreSQL concurrency/idempotency/tenant integration tests in `tests/integration/test_planning_schema.py`.
- [x] T006 Implement planning service/routes/schemas in `src/uribap_api/application/planning_service.py`, `src/uribap_api/api/plans.py`, and `src/uribap_api/api/plan_schemas.py`.
- [x] T007 Add API errors/OpenAPI coverage and update `openapi/openapi.json`.
- [x] T008 Run full API testing skill gates and record evidence in `specs/005-meal-planning/quickstart.md`.
- [x] T009 Write `specs/005-meal-planning/converge.md` and track remaining work.
