---

description: "Task list for API feature 018: household diners and memory"
---

# Tasks: Household Diners and Memory

**Input**: Design documents from `specs/018-household-memory/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, and `contracts/`

**Tests**: Explicitly required by the feature brief. Author regression tests first and ensure they
fail before adding product implementation.

**Organization**: The three user stories are independently testable. Shared regression tests are a
foundational test-first gate because both diner and memory resources use the same migration,
household-scoped service boundary, and event/idempotency infrastructure.

## Phase 1: Setup

**Purpose**: Point Spec Kit at the new feature and reuse the existing UV, API, PostgreSQL, migration,
and OpenAPI infrastructure.

- [x] T001 Set `.specify/feature.json` to `specs/018-household-memory` and complete the feature
  artifacts in `specs/018-household-memory/`.

## Phase 2: Foundational Test-First Gate

**Purpose**: Write all shared and story-specific regression tests before persistence, service, REST,
or MCP implementation.

- [x] T002 [P] Add `MemoryKind`, diner-name, memory-content, and request-schema validation tests in
  `tests/unit/domain/test_household_memory.py`.
- [x] T003 [P] Add PostgreSQL diner create/list/update/archive, name and member-link uniqueness,
  active-membership validation, stale-version, cross-household, event-privacy, and idempotent-replay
  cases in `tests/integration/test_household_memory_service.py`.
- [x] T004 [P] Add PostgreSQL memory create/list/update/archive/profile, scope ordering, archived
  diner filtering, stale-version, cross-household, privacy-event, and idempotent-replay cases in
  `tests/integration/test_household_memory_service.py`.
- [x] T005 [P] Add authenticated REST coverage for every diner, memory, and profile endpoint,
  including `401`, `404`, `409`, and `422` response shapes, in
  `tests/integration/test_household_memory_routes.py` and
  `tests/api/test_household_memory_routes.py`.
- [x] T006 [P] Add MCP memory tool discovery, annotations, name resolution, unknown-name errors,
  context-profile, and archive tests in `tests/integration/test_mcp_memory_tools.py`; update tool
  list expectations in `tests/integration/test_mcp_transport.py`.
- [x] T007 Add migration revision/schema assertions in
  `tests/integration/test_household_memory_migration.py`.

**Checkpoint**: All feature regressions are authored and fail against the current API before
implementation begins.

---

## Phase 3: User Story 1 - Manage who eats in the household (Priority: P1) 🎯 MVP

**Goal**: Create account-linked or account-less diner profiles and update/archive them with
household isolation, uniqueness, and optimistic version checks.

**Independent Test**: Run the diner cases in
`tests/integration/test_household_memory_service.py` and
`tests/integration/test_household_memory_routes.py`.

### Implementation for User Story 1

- [x] T008 [US1] Add `MemoryKind` and the `HouseholdDiner`/`HouseholdMemory` persistence models,
  constraints, and indexes in `src/uribap_api/domain/household/memory.py` and
  `src/uribap_api/infrastructure/persistence/household_models.py`.
- [x] T009 [US1] Add the reversible household-memory Alembic migration after revision
  `d3c72b91a84f` in `migrations/versions/`.
- [x] T010 [US1] Add trimmed diner and memory request schemas plus diner/memory/profile response
  models in `src/uribap_api/api/memory_schemas.py`.
- [x] T011 [US1] Implement tenant-scoped diner create, list, version-checked update, and idempotent
  archive behavior in `src/uribap_api/application/memory_service.py`.
- [x] T012 [US1] Expose `GET/POST /diners` and `PATCH/DELETE /diners/{diner_id}` with active
  household membership and standard error responses in `src/uribap_api/api/memory.py` and mount
  the router in `src/uribap_api/api/router.py`.

**Checkpoint**: Active members can manage account-linked and unlinked diner profiles without
cross-household access.

---

## Phase 4: User Story 2 - Save durable preferences and household notes (Priority: P1)

**Goal**: Create, list, update, and archive validated memories attached to a diner or the household.

**Independent Test**: Run the memory-service cases in
`tests/integration/test_household_memory_service.py` and memory REST cases in
`tests/integration/test_household_memory_routes.py`.

### Implementation for User Story 2

- [x] T013 [US2] Implement household/diner memory create, filtered listing, version-checked update,
  archive, and privacy-minimized domain events in
  `src/uribap_api/application/memory_service.py` and add the six event kinds in
  `src/uribap_api/domain/events/policies.py`.
- [x] T014 [US2] Expose `GET/POST /memories` and `PATCH/DELETE /memories/{memory_id}` with
  `Idempotency-Key`, exact scope/archive/limit semantics, and standard error responses in
  `src/uribap_api/api/memory.py`.

**Checkpoint**: Household and diner memory operations are tenant-scoped, versioned, soft-archived,
idempotent on create, and never place personal text in event payloads or logs.

---

## Phase 5: User Story 3 - Read and operate on memory through the household agent (Priority: P1)

**Goal**: Provide one active-only memory profile and MCP tools that read and maintain diner and
household memory within the authenticated household.

**Independent Test**: Run `tests/integration/test_mcp_memory_tools.py` and
`tests/integration/test_mcp_transport.py`; compare the MCP profile with
`GET /api/v1/memory/profile`.

### Implementation for User Story 3

- [x] T015 [US3] Implement household-first memory listing and active-only
  `HouseholdMemoryProfile` assembly in `src/uribap_api/application/memory_service.py`; expose
  `GET /memory/profile` in `src/uribap_api/api/memory.py`.
- [x] T016 [US3] Add and register `uribap_get_memory`, `uribap_add_diner`,
  `uribap_update_diner`, `uribap_archive_diner`, `uribap_remember`, `uribap_update_memory`, and
  `uribap_forget_memory` in `src/uribap_api/mcp/tools_memory.py` and `src/uribap_api/mcp/server.py`.
- [x] T017 [US3] Add the active memory profile and required description sentence to
  `uribap_get_context` in `src/uribap_api/mcp/tools_household.py`.

**Checkpoint**: REST and MCP expose equivalent active profile data; the agent can resolve a diner
name only within its authenticated household.

---

## Phase 6: Polish and Cross-Cutting Concerns

**Purpose**: Generate and verify the public contract, validate all user stories, and record
convergence.

- [x] T018 Regenerate `openapi/openapi.json` with the repository exporter and extend API contract
  assertions in `tests/api/test_household_memory_routes.py`.
- [x] T019 Run focused tests, migration upgrade/downgrade/upgrade and one-head checks, Ruff,
  touched-file format checks, Pyright, OpenAPI export/check, and the final full suite as specified
  in `specs/018-household-memory/plan.md`.
- [x] T020 Record implementation, ordered verification evidence, migration/contract changes, and
  any deviations in `specs/018-household-memory/converge.md`.

---

## Phase 7: Devin Review Follow-up

**Purpose**: Close the API C findings on retry-safe MCP writes, explicit unlinking, serialized diner
validation, batched profile reads, and member-link error identity.

- [x] T021 Add caller-supplied idempotency keys to `uribap_add_diner` and `uribap_remember`, with
  replay and length validation coverage.
- [x] T022 Add explicit diner unlinking to `uribap_update_diner`, including omitted, unlink, and
  conflicting-input cases.
- [x] T023 Lock diner validation during memory creation and reassignment; verify creation,
  reassignment, and archive serialize on the same diner row.
- [x] T024 Load the active household/diner memory profile in one query, preserve ordering, and use
  `invalid_member_link` for inactive, foreign, and already-linked accounts without changing status
  or detail.
- [x] T025 Run the API C review verification and document its results in this convergence record.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Reuses the existing repository structure and tools.
- **Foundational test-first gate (Phase 2)**: All regression tests must exist and fail before
  production code is added.
- **User Story 1 (Phase 3)**: Creates the shared tables and provides diner CRUD.
- **User Story 2 (Phase 4)**: Uses the shared persistence/schema foundation from US1.
- **User Story 3 (Phase 5)**: Builds the profile from US1/US2 and exposes it through REST/MCP.
- **Polish (Phase 6)**: Depends on all three stories.

### User Story Dependencies

- **US1 (P1)**: Independently testable after the shared schema/migration implementation.
- **US2 (P1)**: Depends on the shared memory table, `MemoryKind`, and request/response schemas
  introduced in US1.
- **US3 (P1)**: Depends on the diner and memory service operations from US1 and US2.

### Parallel Opportunities

- T002, T003, T004, T005, and T006 can be authored in separate test files during the test-first
  gate; T007 is the migration-focused regression.
- After T008–T010, diner and memory service tests can be debugged independently, but the shared
  persistence migration must remain one revision.
- T016 and T017 touch separate MCP modules and may be implemented in parallel after the shared
  profile service is available.

## Implementation Strategy

### MVP First

US1 establishes diner identities for account holders and account-less household eaters. Complete its
REST and service tests first, then add durable memories and agent access without changing meal
forecasting or the Web application.

### Incremental Delivery

1. Write all requested unit, integration, API, MCP, and migration tests and confirm they fail.
2. Add the shared diner/memory schema and migration, then complete diner CRUD (US1).
3. Add household/diner memory CRUD and events (US2).
4. Add the combined active profile and MCP tools/context (US3).
5. Regenerate OpenAPI, run the required checks, and document convergence.

## Notes

- Every task uses a checkbox, sequential id, optional `[P]`, story label for story-phase work, and
  concrete file paths.
- No Web source or automated LLM extraction is in scope.
- A memory body and diner display name MUST NOT be included in event payloads or log output.
