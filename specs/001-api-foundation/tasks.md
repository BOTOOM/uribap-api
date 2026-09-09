---
description: "Executable tasks for the Uribap API foundation"
---

# Tasks: API Foundation

**Input**: Design documents from `specs/001-api-foundation/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Model policy**: primary Luna, implementation Sol, review Terra, artifact analysis GLM-5.3,
routine fixes SWE-1.7; Kimi K3 only with explicit large-artifact escalation.

## Phase 1: Setup

**Purpose**: Create the runnable Python service skeleton and reproducible dependency/tooling baseline.

- [X] T001 Initialize `pyproject.toml` with Python 3.14, FastAPI, Uvicorn, Pydantic Settings, SQLAlchemy, psycopg, Alembic, and pinned development tools using `uv`.
- [X] T002 [P] Configure Ruff, Pyright, pytest, pytest-asyncio, coverage, and test markers in `pyproject.toml`.
- [X] T003 [P] Create `Dockerfile`, `compose.yml`, `.dockerignore`, and `.env.example` for the API/PostgreSQL development environment.
- [X] T004 [P] Create `src/uribap_api/__init__.py`, `src/uribap_api/main.py`, and the package directories from `specs/001-api-foundation/plan.md`.

## Phase 2: Foundational

**Purpose**: Blocking runtime, persistence, safety, and contract infrastructure.

**Checkpoint**: No user-story implementation starts until this phase passes its unit, integration,
API, Docker, and contract checks.

- [X] T005 Implement validated environment configuration in `src/uribap_api/config.py` with safe startup errors and no secret logging.
- [X] T006 [P] Implement bounded SQLAlchemy/psycopg engine and session lifecycle in `src/uribap_api/infrastructure/database.py`.
- [X] T007 [P] Configure structured redacted logging and request-id context in `src/uribap_api/infrastructure/logging.py`.
- [X] T008 Configure Alembic in `alembic.ini`, `migrations/env.py`, and `migrations/versions/` with an empty reviewed baseline migration.
- [X] T009 Implement application factory, versioned router, dependency wiring, and startup/shutdown lifecycle in `src/uribap_api/api/router.py`, `src/uribap_api/api/dependencies.py`, and `src/uribap_api/main.py`.
- [X] T010 Implement Problem Details error types/handlers in `src/uribap_api/domain/shared/errors.py` and `src/uribap_api/api/errors.py`.
- [X] T011 Implement `GET /api/v1/health/live` and `GET /api/v1/health/ready` in `src/uribap_api/api/health.py` with OpenAPI response models.
- [X] T012 Create deterministic OpenAPI export/check tooling in `src/uribap_api/tools/export_openapi.py` and write `openapi/openapi.json`.

## Phase 3: User Story 1 - Start a Reliable API Environment (Priority: P1)

**Goal**: A contributor can start the service, observe safe health states, and stop it predictably.

**Independent Test**: Start Compose from a clean environment, call liveness/readiness, stop the
database, call readiness again, and verify safe 503 behavior.

### Tests for User Story 1

- [X] T013 [P] [US1] Add health contract tests for liveness/readiness and dependency failure in `tests/api/test_health.py`.
- [X] T014 [P] [US1] Add configuration failure/redaction tests in `tests/unit/test_config.py` and `tests/unit/test_logging.py`.
- [X] T015 [US1] Add Compose health smoke coverage and documented expected output in `tests/integration/test_compose_health.py`.

### Implementation for User Story 1

- [X] T016 [US1] Complete safe liveness/readiness response models and dependency checks in `src/uribap_api/api/health.py` to satisfy T013.
- [X] T017 [US1] Complete startup configuration validation and redacted failure handling in `src/uribap_api/config.py` and `src/uribap_api/infrastructure/logging.py` to satisfy T014.
- [X] T018 [US1] Complete Docker healthchecks, non-root runtime, and documented startup/shutdown commands in `Dockerfile`, `compose.yml`, and `specs/001-api-foundation/quickstart.md` to satisfy T015.

**Checkpoint**: US1 is independently demonstrable without business-domain tables.

## Phase 4: User Story 2 - Rebuild and Validate the Persistence Baseline (Priority: P1)

**Goal**: An empty PostgreSQL database reaches a reproducible migration head and test layers are distinct.

**Independent Test**: Apply migrations to an empty database twice, run unit/integration/API test
markers, and verify deterministic results.

### Tests for User Story 2

- [X] T019 [P] [US2] Add migration-from-empty and idempotent-head tests in `tests/integration/test_migrations.py`.
- [X] T020 [P] [US2] Add session/pool lifecycle tests in `tests/integration/test_database.py`.
- [X] T021 [US2] Add test-layer command validation and coverage configuration checks in `tests/unit/test_test_configuration.py`.

### Implementation for User Story 2

- [X] T022 [US2] Finalize the empty baseline revision and Alembic environment in `migrations/versions/` and `migrations/env.py` to satisfy T019.
- [X] T023 [US2] Finalize transaction/session cleanup and bounded pool settings in `src/uribap_api/infrastructure/database.py` to satisfy T020.
- [X] T024 [US2] Finalize pytest markers, fixtures, test database settings, and coverage thresholds in `pyproject.toml` and `tests/conftest.py` to satisfy T021.

**Checkpoint**: US2 is independently demonstrable against PostgreSQL without domain entities.

## Phase 5: User Story 3 - Consume a Stable API Boundary (Priority: P1)

**Goal**: Web can consume a deterministic OpenAPI contract with safe errors and decimal-safe future values.

**Independent Test**: Export the contract twice, compare snapshots, exercise malformed input, and
validate the documented Problem Details shape.

### Tests for User Story 3

- [X] T025 [P] [US3] Add Problem Details contract tests for validation, unknown route, and dependency failure in `tests/api/test_errors.py`.
- [X] T026 [P] [US3] Add OpenAPI determinism and required component checks in `tests/api/test_openapi.py`.
- [X] T027 [P] [US3] Add contract fixture validation for decimal quantity and future mutation metadata in `tests/unit/test_contract_values.py`.

### Implementation for User Story 3

- [X] T028 [US3] Finalize error envelope serialization, correlation IDs, and secret redaction in `src/uribap_api/api/errors.py` and `src/uribap_api/infrastructure/logging.py` to satisfy T025.
- [X] T029 [US3] Finalize OpenAPI export normalization and snapshot comparison in `src/uribap_api/tools/export_openapi.py` and `openapi/openapi.json` to satisfy T026.
- [X] T030 [US3] Add shared quantity/page/mutation contract schemas in `src/uribap_api/api/schemas.py` and document them in `contracts/foundation-api.md` to satisfy T027.

**Checkpoint**: US3 is independently demonstrable by a separate Web consumer.

## Phase 6: Polish and Cross-Cutting Concerns

- [X] T031 [P] Run Ruff, Pyright, all pytest layers, OpenAPI check, and Docker build; record results in `specs/001-api-foundation/quickstart.md`.
- [X] T032 [P] Add dependency/license/secret scan commands to `.github/workflows/ci.yml` without exposing secrets.
- [X] T033 Review resource usage, connection pool limits, and one-worker runtime configuration in `Dockerfile`, `compose.yml`, and `docs/operations/foundation.md`.
- [ ] T034 Run `speckit-analyze` with `glm-5-3-max`, resolve any artifact drift, and update `specs/001-api-foundation/plan.md` if decisions changed. The non-interactive Devin invocation was blocked because sandbox prerequisites are unavailable; no files were modified by the attempted analysis.

## Dependencies and Execution Order

- Phase 1 precedes Phase 2; Phase 2 blocks all user stories.
- US1, US2, and US3 depend on Phase 2 and can be developed in parallel after it, but files shared
  by health/error/contract infrastructure must be changed sequentially.
- Tests in each story precede the implementation tasks that satisfy them.
- T031-T034 run after all desired stories and are the release gate.

## Parallel Opportunities

- T002-T004 can run in parallel after T001.
- T006-T008 can run in parallel after T005 where files do not overlap.
- T013-T015, T019-T021, and T025-T027 can each run in parallel before their story implementation.
- T032 can run in parallel with T033 after core validation.

## Implementation Strategy

1. Complete Phase 1 and Phase 2.
2. Complete US1 and validate the runnable service.
3. Complete US2 and validate empty-database reproducibility.
4. Complete US3 and publish the contract snapshot.
5. Run the cross-cutting gate and only then scaffold domain specs.
