---
description: "Task list for ingredient catalog pagination"
---

# Tasks: Ingredient Catalog Pagination

**Input**: Design documents from `specs/020-ingredient-pagination/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`, and
`quickstart.md`

**Tests**: Explicitly required by the feature brief and API constitution. Add each regression before
its corresponding implementation and confirm the test fails for the missing behavior.

**Organization**: Tasks are grouped by the P1 user stories in `spec.md`.

## Format: `- [ ] [ID] [P?] [Story?] Description with file path`

- **[P]**: The task can run in parallel with other marked tasks because it edits a different file
  and has no dependency on unfinished work.
- **[Story]**: User-story label for story-phase tasks.
- Paths are relative to the repository root.

## Phase 1: Setup

**Purpose**: Shared project initialization.

The API repository, UV environment, PostgreSQL integration setup, OpenAPI exporter, and test
fixtures already exist. No dependency, project initialization, or database migration is required.

## Phase 2: Foundational

**Purpose**: Add the requested regression suite before any product implementation.

No new shared infrastructure is needed; the existing `PageInfo`, `DomainError`, household scoping,
and PostgreSQL fixtures are reused. These feature-wide tests are blocking prerequisites for the
story implementation phases.

- [x] T001 [P] Add service and REST integration regressions for a two-page `limit=2` traversal
  across tied normalized names, complete traversal of 140 ingredients, no gaps or duplicates, a
  null final cursor, malformed/invalid/structurally incomplete cursors returning `422` Problem
  Details, `query`/`dimension`/`include_global` continuation, and an empty filtered final page in
  `tests/integration/test_ingredient_routes.py`.
- [x] T002 [P] Add OpenAPI assertions for the optional cursor query parameter and typed ingredient
  `PageInfo` response in `tests/api/test_openapi.py`.
- [x] T003 [P] Add MCP continuation coverage for `query`, `dimension`, and `include_global`,
  including preserved `items` and page-local `count`, in
  `tests/integration/test_mcp_ingredients.py`.

---

## Phase 3: User Story 1 - Retrieve a complete ingredient catalog (Priority: P1)

**Goal**: Let REST clients traverse a large ingredient catalog in deterministic pages, including
same-name ties, and recognize the final page.

**Independent Test**: Traverse a seeded catalog with `limit=2`; verify all rows appear once in
`(normalized_name, id)` order and the last response has a null cursor.

### Implementation for User Story 1

- [x] T004 [US1] Implement cursor validation/encoding, composite keyset ordering, and `limit + 1`
  page construction in `src/uribap_api/application/ingredient_service.py`.
- [x] T005 [US1] Expose the optional cursor in `src/uribap_api/api/ingredients.py` and type the
  ingredient response `page_info` with the shared `PageInfo` in
  `src/uribap_api/api/recipe_schemas.py`.
- [x] T006 [US1] Regenerate the canonical REST contract at `openapi/openapi.json` using
  `PYTHONPATH=src uv run python -m uribap_api.tools.export_openapi`.

**Checkpoint**: REST clients can retrieve a complete unchanged catalog and distinguish its final
page.

---

## Phase 4: User Story 2 - Continue a filtered ingredient search (Priority: P1)

**Goal**: Keep search, dimension, and global-inclusion predicates effective on every cursor page.

**Independent Test**: Continue a filtered listing with the same filters and cursor; verify each
returned item matches the filters and every matching item is included.

### Implementation for User Story 2

- [x] T007 [US2] Apply the existing household/global visibility, query, and dimension predicates
  before the composite cursor boundary in `src/uribap_api/application/ingredient_service.py`.

**Checkpoint**: Every filtered REST traversal retains the same result set while using the same
filters on later requests.

---

## Phase 5: User Story 3 - Traverse the catalog through MCP (Priority: P1)

**Goal**: Provide cursor traversal through the MCP listing tool without removing its existing
`items` and page-local `count` fields.

**Independent Test**: Retrieve a multi-page catalog through MCP; verify each page retains `items`
and `count`, advances with `next_cursor`, and ends with `next_cursor: null`.

### Implementation for User Story 3

- [x] T008 [US3] Add the optional cursor argument and return `next_cursor` from
  `uribap_list_ingredients` while preserving existing fields in
  `src/uribap_api/mcp/tools_catalog.py`.

**Checkpoint**: MCP clients can traverse the same filtered ingredient listing without a breaking
response change.

---

## Phase 6: Polish and cross-cutting concerns

**Purpose**: Validate and document the complete API feature.

- [x] T009 Run the feature's REST, filter, MCP, OpenAPI, Ruff, and Pyright checks from
  `specs/020-ingredient-pagination/quickstart.md` and the `/uribap-api-testing` workflow.
- [x] T010 Record actual verification results, skips, and any environment blockers in
  `specs/020-ingredient-pagination/converge.md`.

---

## Dependencies and Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No new setup is needed.
- **Foundational (Phase 2)**: No new infrastructure is needed; existing API facilities are
  reused.
- **User Story 1 (Phase 3)**: Independent P1 increment; establishes REST keyset pagination.
- **User Story 2 (Phase 4)**: Depends on the cursor service from US1; adds filter-continuation
  acceptance coverage.
- **User Story 3 (Phase 5)**: Depends on the shared cursor service from US1 and filtered query
  semantics from US2.
- **Polish (Phase 6)**: Depends on all three user stories.

### User Story Dependencies

- **US1**: No feature dependency; the existing repository infrastructure is sufficient.
- **US2**: Depends on US1's service cursor and deterministic ordering.
- **US3**: Depends on US1's service page result and US2's retained filter behavior.

### Parallel Opportunities

- T001 and T002 may be authored in parallel because they modify different test files.
- Once the service result contract is set in T004, route/schema work can proceed in its own file
  group; OpenAPI generation follows those changes.
- MCP test authoring in T003 uses a separate file from REST tests, but MCP implementation depends on
  the shared service result.
- No user story is independent of the shared cursor service after US1.

---

## Parallel Example: User Story 1

```text
Task: T001 — REST/service regressions in tests/integration/test_ingredient_routes.py
Task: T002 — OpenAPI contract regression in tests/api/test_openapi.py
Task: T003 — MCP continuation regression in tests/integration/test_mcp_ingredients.py
```

---

## Implementation Strategy

### MVP First

1. Add and fail the US1 REST and OpenAPI regressions.
2. Add and fail the filtered REST and MCP continuation regressions.
3. Implement the common cursor service, REST response, and MCP adapter.
4. Validate each user story with its focused tests.

### Incremental Delivery

1. Complete US1 to deliver deterministic REST pages.
2. Add US2 filter-continuation coverage and preserve the existing predicates.
3. Add US3 MCP cursor support while retaining `items` and `count`.
4. Run the API verification workflow and record actual results in `converge.md`.

## Notes

- Regression tests precede their corresponding product-code changes.
- [P] indicates separate files and no unfinished-task dependency.
- The cursor is stateless; no migration or new dependency is expected.
- Run Python tools and tests with `uv run`; regenerate OpenAPI only with the repository exporter.
