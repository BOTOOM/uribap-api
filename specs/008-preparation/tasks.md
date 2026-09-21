# Tasks: Preparation

- [x] T001 [P] Complete analyze/checklist traceability in `specs/008-preparation/analyze.md` and `traceability.md`.
- [x] T002 [P] Add pure policy tests in `tests/unit/domain/test_preparation_policies.py` (transitions, due_at per meal type and lead, invalid timezone fallback, fingerprint stability, manual-task validation). — 9 tests
- [x] T003 Implement `src/uribap_api/domain/preparation/policies.py`.
- [x] T004 Add `preparation_models.py`, migration `a8e4b2c1d603_preparation_tasks` (task + operation tables + `uq_meal_plan_entry_household`), and register models in `migrations/env.py`.
- [x] T005 Add `tests/integration/test_preparation_schema.py` (checks, composite FK, derived-fingerprint uniqueness, operation uniqueness). — 5 tests
- [x] T006 Implement rule management on recipe versions (draft-only) in `preparation_service.py`/`preparation_schemas.py`/`recipes.py`. (`POST|DELETE /recipes/{id}/versions/{vid}/preparation-rules`)
- [x] T007 Implement `preparation_service.py` (approve-time derivation, manual create, transitions, receipts) plus `preparation_schemas.py` and `preparation.py` routes; derivation hooked into `transition_plan` APPROVE.
- [x] T008 Add `tests/integration/test_preparation_service.py` (8 tests) and `tests/api/test_preparation_routes.py` contract test.
- [x] T009 Regenerate `openapi/openapi.json`; contract already matches `contracts/preparation.md`.
- [x] T010 Run full API gates and record `specs/008-preparation/quickstart.md`.
- [x] T011 Write `specs/008-preparation/converge.md`.
