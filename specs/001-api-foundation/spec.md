# Feature Specification: API Foundation

**Feature Branch**: `001-api-foundation`

**Created**: 2026-09-08

**Status**: Draft

**Input**: Establish the Dockerized FastAPI backend foundation, PostgreSQL integration, deterministic domain boundaries, testing tooling, and canonical OpenAPI contract for Uribap.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Start a Reliable API Environment (Priority: P1)

As a developer working on Uribap, I need one documented local command path to start the backend
and its development database so that every contributor works against the same baseline.

**Why this priority**: No domain feature can be implemented or reviewed reliably without a
repeatable environment and observable service health.

**Independent Test**: From a clean checkout with the documented prerequisites, a contributor
starts the development environment, observes the service health states, and stops it without
manual database setup.

**Acceptance Scenarios**:

1. **Given** a clean checkout and valid non-secret environment values, **When** the contributor
   starts the documented development environment, **Then** the API and database reach healthy
   states and the API exposes its documented health responses.
2. **Given** the database is unavailable, **When** the contributor checks service health,
   **Then** liveness and readiness distinguish process availability from dependency readiness
   and return an actionable status without leaking credentials.

---

### User Story 2 - Rebuild and Validate the Persistence Baseline (Priority: P1)

As a backend developer, I need to create the database schema from an empty database and run the
same validation suite in local and continuous-integration environments so that future domain
changes are reproducible and reviewable.

**Why this priority**: Inventory and consumption correctness depend on migration history and
repeatable tests before any business table is added.

**Independent Test**: Against an empty PostgreSQL database, the contributor applies migrations,
runs the backend test layers, and obtains the same schema/contract result twice.

**Acceptance Scenarios**:

1. **Given** an empty supported database, **When** migrations are applied from the repository,
   **Then** the schema reaches the expected head without manual SQL or hidden state.
2. **Given** the same source revision and database version, **When** the validation suite runs
   twice, **Then** it produces deterministic results and identifies unit, integration, and API
   failures separately.

---

### User Story 3 - Consume a Stable API Boundary (Priority: P1)

As a frontend developer, I need a canonical API description with predictable errors and data
representation so that the Web repository can generate a client without duplicating backend
assumptions.

**Why this priority**: The two public repositories require an explicit boundary before feature
work can proceed independently.

**Independent Test**: A consumer obtains the published contract, generates a client, exercises
health and error examples, and detects an intentional contract change through validation.

**Acceptance Scenarios**:

1. **Given** a successful API build, **When** the contract is generated, **Then** its routes,
   response shapes, error format, decimal quantity representation, and version are stable and
   reproducible.
2. **Given** an invalid request or unavailable dependency, **When** the API responds, **Then** it
   returns a documented error shape with a correlation identifier and no secret or token data.

---

### Edge Cases

- Missing required configuration MUST stop startup with a safe, actionable message rather than
  silently selecting insecure defaults.
- A database that is reachable but has not been migrated MUST be reported as not ready.
- Re-running migration and startup commands MUST be safe and must not duplicate schema objects.
- A client requesting an unsupported media type, malformed JSON, or an unknown route MUST receive
  the documented error envelope.
- A contract generation step with uncommitted or nondeterministic output MUST fail validation.
- Logs and health responses MUST remain safe when connection strings or authorization headers are
  present in the failing request.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The project MUST provide a documented, repeatable path for starting and stopping
  the backend development environment and its database dependency.
- **FR-002**: The service MUST expose separate liveness and readiness states that distinguish
  process availability from required dependency availability.
- **FR-003**: Configuration MUST be validated at startup and MUST fail safely when required
  values are absent or malformed; secrets MUST never be committed or emitted in logs.
- **FR-004**: The persistence baseline MUST be creatable from an empty supported database using
  versioned, reviewed migrations with no manual SQL steps.
- **FR-005**: The project MUST separate transport handling, application use cases, deterministic
  domain services, and persistence responsibilities so routes do not own domain calculations.
- **FR-006**: The project MUST publish a canonical, reproducible API contract for every exposed
  route, including health, errors, quantities, pagination, idempotency, and concurrency fields
  introduced by the foundation.
- **FR-007**: API errors MUST use one documented envelope with stable machine-readable type,
  human-readable detail, status, and correlation information where applicable.
- **FR-008**: Quantity values in the contract MUST preserve decimal precision and an explicit unit;
  the foundation MUST NOT encode quantities as binary floating-point values.
- **FR-009**: The validation suite MUST distinguish pure domain/unit checks, database integration
  checks, and HTTP/API contract checks.
- **FR-010**: The development and production images MUST have documented health checks, a
  non-secret environment contract, and a bounded runtime configuration suitable for the shared
  VPS budget.
- **FR-011**: Structured logs MUST include enough context to diagnose a request or migration
  failure while redacting authorization data, credentials, and unnecessary personal data.
- **FR-012**: The foundation MUST not introduce a resident queue, cache, or background worker;
  any later asynchronous process MUST be justified by a measured requirement.

### Key Entities

- **API service**: The backend process and its documented health/readiness states.
- **Configuration contract**: Required environment values and safe startup validation rules.
- **Persistence baseline**: The database schema version and ordered migration history.
- **API contract**: The versioned description of routes, request/response shapes, errors, and
  compatibility expectations consumed by the Web repository.
- **Validation suite**: Separated checks for pure logic, persistence integration, and HTTP/API
  behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new contributor can start the documented local API environment from a clean
  checkout in 5 minutes or less after prerequisites are installed.
- **SC-002**: Liveness responds within 500ms when the process is available, and readiness reports
  an unavailable database within 2 seconds without exposing credentials.
- **SC-003**: Applying migrations to an empty database twice from the same revision produces the
  same schema head and no duplicate-object errors.
- **SC-004**: The contract generation/check step produces no uncommitted diff when run twice from
  the same source revision.
- **SC-005**: The foundation validation suite passes in a clean environment and reports failures
  by unit, integration, and API layer.
- **SC-006**: A repository secret scan finds zero credentials, tokens, or private key material in
  tracked foundation files.
- **SC-007**: Under the documented development workload, the API foundation remains below the
  agreed 1GB Uribap service budget and uses a bounded database connection pool.

## Assumptions

- PostgreSQL is the only required persistence dependency for this foundation feature.
- Identity provider integration, household tables, and business-domain tables belong to later
  specs; this feature defines boundaries and extension points only.
- Brevo, ZITADEL, and production DNS are configured in the identity/deployment specs, not here.
- The API repository is public; all examples use placeholders and no real secrets.
- The Web repository consumes a pinned contract snapshot rather than importing backend source.
