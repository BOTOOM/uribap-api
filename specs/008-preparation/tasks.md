# Tasks: Preparation

- [ ] T001 [P] Complete analyze/checklist traceability in `specs/008-preparation/analyze.md` and `traceability.md`.
- [ ] T002 [P] Add pure policy tests in `tests/unit/domain/test_preparation_policies.py` (transitions, due_at per meal type and lead, invalid timezone fallback, fingerprint stability, manual-task validation).
- [ ] T003 Implement `src/uribap_api/domain/preparation/policies.py`.
- [ ] T004 Add `preparation_models.py`, migration `preparation_tasks` (task + operation tables + `uq_meal_plan_entry_household`), and register models in `migrations/env.py`.
- [ ] T005 Add `tests/integration/test_preparation_schema.py` (checks, composite FK, derived-fingerprint uniqueness, operation uniqueness).
- [ ] T006 Implement rule management on recipe versions (draft-only) in `recipe_service.py`/`recipe_schemas.py`/`recipes.py`.
- [ ] T007 Implement `preparation_service.py` (approve-time derivation, manual create, transitions, receipts) plus `preparation_schemas.py` and `preparation.py` routes; hook derivation into `transition_plan` APPROVE.
- [ ] T008 Add `tests/integration/test_preparation_service.py` and API route contract tests.
- [ ] T009 Regenerate `openapi/openapi.json` and update `contracts/preparation.md`.
- [ ] T010 Run full API gates and record `specs/008-preparation/quickstart.md`.
- [ ] T011 Write `specs/008-preparation/converge.md`.
