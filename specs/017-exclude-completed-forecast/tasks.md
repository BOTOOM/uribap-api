---

description: "Task list for feature 017: completed meal outcomes and plan entry detail"
---

# Tasks: Completed Meal Outcomes and Plan Entry Detail

**Input**: Design documents from `specs/017-exclude-completed-forecast/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, and `contracts/`

**Tests**: Required by the feature brief. Write regression tests before the corresponding
implementation changes and use the existing PostgreSQL integration fixture.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup

**Purpose**: Reuse the existing UV, PostgreSQL integration fixture, API routing, and OpenAPI
exporter. No new package or project initialization is required.

## Phase 2: Foundational

**Purpose**: No shared infrastructure change is needed. The stories use the existing completion,
planning, migration, test-session, and MCP infrastructure.

---

## Phase 3: User Story 1 - Resolved meals no longer create demand (Priority: P1) 🎯 MVP

**Goal**: Exclude each approved plan entry with a household-scoped recorded completion from
forecast and shopping demand while keeping plan traceability and restoring demand after reopen.

**Independent Test**: PostgreSQL forecast tests cover pending, cooked-recorded, skipped-recorded,
reopened, mixed, cross-household, and all-resolved approved-plan entries.

### Tests for User Story 1

> Write these tests before changing the forecast query.

- [x] T001 [P] [US1] Add forecast integration cases for pending, recorded cooked, reopened, mixed, cross-household, and all-resolved entries in `tests/integration/test_forecast_service.py`

### Implementation for User Story 1

- [x] T002 [US1] Exclude entries with a household-scoped recorded completion using correlated `NOT EXISTS` in `src/uribap_api/application/forecast_service.py`, preserving `considered_plan_ids`

**Checkpoint**: Resolved entries no longer contribute demand; reopening restores demand through the canonical forecast used by shopping.

---

## Phase 4: User Story 2 - Record a meal that was not cooked at home (Priority: P1)

**Goal**: Add a recorded `skipped` completion outcome and skip endpoint that creates no completion
lines or inventory movements, supports idempotency, and can be reopened.

**Independent Test**: PostgreSQL service, route, and MCP tests cover skip outcomes, unchanged lot
amounts, error statuses, idempotent replay, and reopen behavior.

### Tests for User Story 2

> Write these tests before the completion model, service, route, or MCP implementation.

- [x] T003 [P] [US2] Add service tests for skip outcome and forecast exclusion/restoration, zero lines and movements, unchanged lots, cooked/skipped conflicts, missing/non-approved/foreign entries, replay and same-key fingerprint conflict, reopen, correction 404, event payload, and cooked response outcome in `tests/integration/test_completion_service.py`
- [x] T004 [P] [US2] Add HTTP skip-route tests for 201, `Idempotency-Key` replay, reason-length validation, missing/foreign-entry 404, non-approved 409, and exact recorded-completion 409 detail in `tests/integration/test_plan_completion_routes.py`
- [x] T005 [P] [US2] Add skip endpoint OpenAPI assertions for request/response, 201, and `Idempotency-Key` in `tests/api/test_completion_routes.py`
- [x] T006 [P] [US2] Add MCP assertions for the exact skip tool name, WRITE annotation, title/description, reason/idempotency arguments and invocation, and cooked-tool demand description in `tests/integration/test_mcp_plan_tools.py`

### Implementation for User Story 2

- [x] T007 [US2] Add `MealCompletionOutcome` and persist `outcome`/`outcome_note` with the outcome check constraint in `src/uribap_api/domain/completion/policies.py` and `src/uribap_api/infrastructure/persistence/completion_models.py`
- [x] T008 [US2] Add the reversible outcome migration with `down_revision = "f2b8d4e6a917"` in `migrations/versions/`
- [x] T009 [US2] Implement `MealCompletionSkip.reason` with a 2000-character maximum, skip validation/idempotency/zero-line persistence/event payload, and `MealCompletionResponse.outcome`/`outcome_note` in `src/uribap_api/application/completion_service.py` and `src/uribap_api/api/completion_schemas.py`
- [x] T010 [US2] Add `POST /{plan_id}/entries/{entry_id}/skip` with 201 response and `Idempotency-Key` handling in `src/uribap_api/api/completion.py`
- [x] T011 [US2] Register `uribap_skip_meal` with the exact WRITE title/description and update `uribap_complete_meal` to describe forecast/shopping demand removal in `src/uribap_api/mcp/tools_plan.py`

**Checkpoint**: Cooked and skipped recorded completions share forecast exclusion; skip changes no inventory and reopen restores demand.

---

## Phase 5: User Story 3 - See what is needed to prepare a planned meal (Priority: P1)

**Goal**: Return one tenant-scoped, read-only plan-entry detail response with scaled recipe
requirements, available stock, shortfalls, recipe metadata, and current recorded completion.

**Independent Test**: PostgreSQL service and route tests verify 4 servings against base 2, lot
availability, line ordering and optional flags, recipe description, completion/reopen state, and
cross-household 404.

### Tests for User Story 3

> Write these tests before the plan-detail service, route, schema, or MCP implementation.

- [x] T012 [P] [US3] Add plan-entry detail integration cases for scaling, available/unavailable lots, shortfalls, optional flags, position/ID ordering, recipe description, recorded/reopened completion, and household isolation in `tests/integration/test_plan_entry_detail.py`
- [x] T013 [P] [US3] Add HTTP detail-route success and 404 cases for missing/foreign plans, entries from another plan, and cross-household entries in `tests/integration/test_plan_entry_detail_routes.py`
- [x] T014 [P] [US3] Add detail path and response-field OpenAPI assertions in `tests/api/test_planning_routes.py`
- [x] T015 [P] [US3] Add MCP assertions for `uribap_get_plan_entry`, READ_ONLY annotation, title, and returned detail coverage in `tests/integration/test_mcp_plan_tools.py`

### Implementation for User Story 3

- [x] T016 [US3] Add detail response and ingredient-line schemas with the specified fields in `src/uribap_api/api/plan_schemas.py`
- [x] T017 [US3] Implement household-scoped read-only `get_entry_detail`, reuse `planned_lines`, and calculate available stock/shortfall in `src/uribap_api/application/planning_service.py`
- [x] T018 [US3] Add `GET /{plan_id}/entries/{entry_id}/detail` in `src/uribap_api/api/plans.py`
- [x] T019 [US3] Register `uribap_get_plan_entry` as READ_ONLY with title `Plan entry detail` and return the detail payload in `src/uribap_api/mcp/tools_plan.py`

**Checkpoint**: REST and MCP detail calls return the same read-only, tenant-scoped scaled recipe/stock projection.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Regenerate the public contract, validate all stories in the prescribed order, and record
convergence.

- [x] T020 Run the focused tests, Alembic upgrade/downgrade/upgrade plus single-head check, Ruff, format check, and Pyright in the order documented in `plan.md`
- [x] T021 Regenerate `openapi/openapi.json` with `src/uribap_api/tools/export_openapi.py`, pass its `--check`, and pass the contract/snapshot test
- [x] T022 Run the final full suite with `uv run pytest -q`
- [x] T023 Record implementation, ordered verification evidence, migration/contract changes, and any deviations in `specs/017-exclude-completed-forecast/converge.md`

Verification exceptions: The repository-wide Ruff format check reports formatting drift confirmed pre-existing on `origin/main`; the reused local database causes the known order-dependent outbox test failure in the full suite. Both results are documented in `converge.md` and were accepted as non-blocking for this push.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Reuse existing tooling and PostgreSQL fixture; no project setup code is added.
- **Foundational (Phase 2)**: No blocking infrastructure change is required.
- **User Story 1 (Phase 3)**: Can be implemented independently against the existing recorded/reopened completion model.
- **User Story 2 (Phase 4)**: Adds completion outcome persistence and depends on the verified migration head.
- **User Story 3 (Phase 5)**: Depends on the completion response outcome fields when embedding a current completion.
- **Polish (Phase 6)**: Depends on all three stories being implemented.

### User Story Dependencies

- **US1 (P1)**: Independent; its forecast filter uses only household, entry id, and recorded state.
- **US2 (P1)**: Independent of US1 implementation; skipped outcomes are excluded by the same recorded-state filter.
- **US3 (P1)**: Depends on US2's extended completion response when embedding a recorded completion.

### Within Each User Story

- Tests are written before their corresponding implementation and cover the independently testable user journey.
- Persistence/model work precedes service behavior that writes or reads the new outcome.
- Services precede API and MCP adapters.
- OpenAPI generation follows all schema and route changes.

### Parallel Opportunities

- US1 forecast tests and US2 service/route/MCP tests can be authored in parallel because they touch separate test files.
- US3 detail service, route, API contract, and MCP tests can be authored in parallel across separate files.
- After the required foundations are in place, US1 forecast implementation can proceed independently of US2 skip implementation.
- US3 implementation follows US2 because detail embeds the updated completion response.

## Parallel Example: Test Authoring

```text
Task: T001 forecast regressions in tests/integration/test_forecast_service.py
Task: T003 skip service regressions in tests/integration/test_completion_service.py
Task: T004 skip HTTP regressions in tests/integration/test_plan_completion_routes.py
Task: T006 skip MCP regressions in tests/integration/test_mcp_plan_tools.py
```

## Implementation Strategy

### MVP

US1 is the smallest independently valuable behavior: recorded cooked or skipped completions do not
contribute future demand, and reopening restores it. The requested feature deliverable includes
US1, US2, and US3.

### Incremental Delivery

1. Add forecast regressions and the recorded-state anti-join (US1).
2. Add outcome persistence, migration, skip service/route, and MCP write tool (US2).
3. Add the read-only scaled plan-entry detail service, route, and MCP read tool (US3).
4. Regenerate OpenAPI, run ordered verification, and record convergence.

## Notes

- Every task is a checklist item with a sequential task ID; user-story tasks use their `[US#]` label.
- `[P]` identifies test tasks that can be authored in separate files without dependencies.
- Use UV for all Python commands; do not start identity, full compose, or unrelated services.
- Commit and push the existing feature branch only after the required verification succeeds.
