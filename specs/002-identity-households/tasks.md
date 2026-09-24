# Tasks: Identity and Households

**Input**: Design documents from `/specs/002-identity-households/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Required by the feature specification and API constitution. Test-first tasks must fail before the corresponding implementation tasks.

**Model policy**: Luna architecture, Sol implementation, Terra security/SQL review, GLM-5.3 artifact analysis, SWE-2 routine fixes; no Kimi K3 without explicit escalation.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish dependencies, local identity configuration boundaries, and test fixtures without secrets.

- [ ] T001 [P] Add `PyJWT[crypto]` and runtime `httpx` dependencies with mature pinned lockfile versions in `pyproject.toml` and `uv.lock`.
- [ ] T002 [P] Add OIDC, identity cache, local SMTP, invitation, and security settings placeholders to `src/uribap_api/config.py`, `.env.example`, and `tests/unit/test_config.py` without secret values.
- [ ] T003 [P] Create canonical local identity Compose skeleton, ignored env template, and scripts directory in `identity/compose.identity.yml`, `identity/.env.identity.example`, and `identity/scripts/`.
- [ ] T004 [P] Add identity test markers, deterministic clock/token fixtures, and synthetic identity helpers in `tests/conftest.py`, `tests/unit/conftest.py`, and `tests/integration/conftest.py`.
- [ ] T005 [P] Add feature API contract test scaffolding in `tests/api/test_identity_household_contract.py` mapped to `contracts/identity-households.md`.

**Checkpoint**: Dependencies and secret-free local configuration boundaries exist; no application behavior is implemented yet.

---

## Phase 2: Foundational Security and Persistence

**Purpose**: Blocking security, persistence, error, audit, and notification primitives required by every user story.

**CRITICAL**: No user story implementation begins until this phase passes its unit and migration checks.

### Tests first

- [ ] T006 [P] Write pure claim validation tests for required claims, algorithm allow-list, issuer, audience, expiry, not-before, subject, scope, malformed tokens, and clock skew in `tests/unit/infrastructure/test_claims.py`.
- [ ] T007 [P] Write pure role/permission policy tests for owner/admin/member actions and last-owner invariants in `tests/unit/domain/test_household_policies.py`.
- [ ] T008 [P] Write pure invitation token/hash/state-transition tests for entropy, mismatch, expiry, revoke, one-time use, and safe redaction in `tests/unit/domain/test_invitation_policies.py`.
- [ ] T009 [P] Write migration/schema integration tests for uniqueness, foreign keys, enum/state constraints, indexes, and append-only audit semantics in `tests/integration/test_identity_schema.py`.
- [ ] T010 [P] Write auth error and logging redaction tests for missing/invalid bearer values and token/secret omission in `tests/api/test_identity_errors.py`.

### Implementation

- [ ] T011 [P] Implement provider-neutral domain identity, household, membership, invitation, and audit value objects/policies in `src/uribap_api/domain/identity/` and `src/uribap_api/domain/household/`.
- [ ] T012 [P] Implement SQLAlchemy declarative persistence models and relationships in `src/uribap_api/infrastructure/persistence/base.py`, `src/uribap_api/infrastructure/persistence/identity_models.py`, and `src/uribap_api/infrastructure/persistence/household_models.py`.
- [ ] T013 Create the reviewed Alembic migration for `app_user`, `user_identity`, `household`, `household_member`, `household_invitation`, `audit_event`, and `email_outbox_entry` in `migrations/versions/`.
- [ ] T014 [P] Implement OIDC/JWKS configuration, async bounded cache, key rotation refresh, timeout, and JWT validator in `src/uribap_api/infrastructure/identity/jwks_cache.py`, `src/uribap_api/infrastructure/identity/claims.py`, and `src/uribap_api/infrastructure/identity/jwt_validator.py`.
- [ ] T015 [P] Add composable authenticated-user, required-scope, and household-membership dependencies in `src/uribap_api/api/dependencies.py`.
- [ ] T016 [P] Extend Problem Details mapping with safe `401`, `403`, `404`, `409`, and identity-provider-unavailable codes in `src/uribap_api/api/errors.py` and `src/uribap_api/domain/shared/errors.py`.
- [ ] T017 [P] Implement append-only audit event and email outbox persistence/application boundaries in `src/uribap_api/application/audit_service.py`, `src/uribap_api/infrastructure/email/outbox.py`, and `src/uribap_api/infrastructure/email/mailer.py`.
- [ ] T018 [P] Add structured redaction rules for Authorization, cookies, invitation tokens, SMTP values, and provider secrets in `src/uribap_api/infrastructure/logging.py` and `tests/unit/test_logging_redaction.py`.

**Checkpoint**: Migration applies to isolated PostgreSQL; pure identity/role/invitation tests and auth error tests pass; no route depends on unvalidated claims.

---

## Phase 3: User Story 1 - Sign in and Establish an Uribap Identity (Priority: P1) 🎯 MVP

**Goal**: Validate local/provider OIDC tokens, provision an internal user idempotently, and expose safe current-user data.

**Independent Test**: Deterministic signed-token tests and local ZITADEL JWKS/API tests prove valid access, invalid claim rejection, identity linking, and repeat/concurrent provisioning.

### Tests first

- [ ] T019 [P] [US1] Write JWT/JWKS unit tests for cache hit, cache miss, unknown key refresh, provider timeout, invalid signature, and issuer/audience rejection in `tests/unit/infrastructure/test_jwt_validator.py`.
- [ ] T020 [P] [US1] Write API contract tests for `GET /api/v1/me`, missing/invalid scopes, disabled users, and safe Problem Details in `tests/api/test_identity_routes.py`.
- [ ] T021 [P] [US1] Write PostgreSQL integration tests for idempotent identity provisioning and concurrent `(issuer, subject)` requests in `tests/integration/test_identity_provisioning.py`.
- [ ] T022 [P] [US1] Write local identity integration tests for discovery, JWKS, valid token validation, wrong issuer/audience/scope, and provider readiness in `tests/integration/test_local_zitadel.py`.

### Implementation

- [ ] T023 [US1] Implement identity provisioning and safe profile synchronization in `src/uribap_api/application/identity_service.py`.
- [ ] T024 [US1] Implement authenticated current-user schemas and routes in `src/uribap_api/api/identity.py` and `src/uribap_api/api/schemas.py`.
- [ ] T025 [US1] Register identity routes and dependency wiring under `/api/v1` in `src/uribap_api/api/router.py` and `src/uribap_api/main.py`.
- [ ] T026 [US1] Add deterministic signed-token fixture helpers that never use production credentials in `tests/unit/fixtures/identity_tokens.py`.
- [ ] T027 [US1] Export and snapshot-check the identity OpenAPI contract in `openapi/openapi.json` and `tests/api/test_openapi_identity.py`.

**Checkpoint**: `GET /me`, JWT validation, identity upsert, and local ZITADEL acceptance pass independently.

---

## Phase 4: User Story 2 - Create and Operate a Household (Priority: P1)

**Goal**: Create tenant households, assign ownership, manage settings/members, enforce role authorization, and protect cross-household isolation.

**Independent Test**: Two synthetic users and two households exercise create/read/update/member list, role denial, version conflicts, and cross-tenant non-disclosure against real PostgreSQL.

### Tests first

- [ ] T028 [P] [US2] Write household API contract tests for create/get/update/member list, validation, pagination, `401`, `403`, safe `404`, and `409` in `tests/api/test_household_routes.py`.
- [ ] T029 [P] [US2] Write service tests for owner/admin/member policy, settings validation, last-owner protection, and optimistic version conflicts in `tests/unit/application/test_household_service.py`.
- [ ] T030 [P] [US2] Write PostgreSQL integration tests for two-household isolation, membership constraints, concurrent updates, and no cross-tenant leakage in `tests/integration/test_tenant_isolation.py`.
- [ ] T031 [P] [US2] Write API tests proving household dependency derives authorization from database membership rather than client claims in `tests/api/test_household_authorization.py`.

### Implementation

- [ ] T032 [P] [US2] Implement household and membership schemas, pagination, version headers, and safe DTOs in `src/uribap_api/api/schemas.py`.
- [ ] T033 [US2] Implement household creation, settings, member listing, and membership authorization services in `src/uribap_api/application/household_service.py`.
- [ ] T034 [US2] Implement household and member routes in `src/uribap_api/api/households.py`.
- [ ] T035 [US2] Add `If-Match`/version and `Idempotency-Key` handling for household/member mutations in `src/uribap_api/api/dependencies.py`, `src/uribap_api/api/households.py`, and `src/uribap_api/application/household_service.py`.
- [ ] T036 [US2] Add API contract and generated OpenAPI assertions for household permission and concurrency behavior in `tests/api/test_household_contract.py` and `openapi/openapi.json`.

**Checkpoint**: Household creation and role-aware, versioned, tenant-isolated operations pass independently.

---

## Phase 5: User Story 3 - Invite and Manage Household Members (Priority: P1)

**Goal**: Create, send, inspect, revoke, accept, and authorize one-time household invitations with auditability.

**Independent Test**: Owner/admin/member tests plus Mailpit and PostgreSQL concurrency tests prove invitation lifecycle, email capture, verified-email matching, retry idempotency, and last-owner safety.

### Tests first

- [ ] T037 [P] [US3] Write invitation API contract tests for create/list/revoke/accept, role limits, safe response redaction, and all documented error codes in `tests/api/test_invitation_routes.py`.
- [ ] T038 [P] [US3] Write invitation service tests for normalization, hashed token lookup, expiration, email matching, atomic consumption, retry idempotency, and role restrictions in `tests/unit/application/test_invitation_service.py`.
- [ ] T039 [P] [US3] Write PostgreSQL concurrency tests for two simultaneous acceptances, duplicate pending invitations, role changes, and last-owner protection in `tests/integration/test_invitation_concurrency.py`.
- [ ] T040 [P] [US3] Write Mailpit integration tests that assert synthetic recipient/subject/link content and prove no external SMTP endpoint is configured in `tests/integration/test_mailpit_flows.py`.

### Implementation

- [ ] T041 [P] [US3] Implement invitation schemas, redacted list DTOs, and acceptance input validation in `src/uribap_api/api/schemas.py`.
- [ ] T042 [US3] Implement invitation creation, resend, revoke, atomic accept, membership creation/reactivation, and owner/admin policy in `src/uribap_api/application/invitation_service.py`.
- [ ] T043 [US3] Implement invitation and membership administration routes in `src/uribap_api/api/invitations.py` and extend `src/uribap_api/api/households.py`.
- [ ] T044 [US3] Implement local/production SMTP adapter and notification dispatch with outbox deduplication in `src/uribap_api/infrastructure/email/mailer.py`.
- [ ] T045 [US3] Register invitation routes, transaction boundaries, and audit events in `src/uribap_api/api/router.py`, `src/uribap_api/application/audit_service.py`, and `src/uribap_api/application/invitation_service.py`.
- [ ] T046 [US3] Add OpenAPI contract coverage for invitation, audit-safe errors, idempotency, and concurrency headers in `tests/api/test_invitation_contract.py` and `openapi/openapi.json`.

**Checkpoint**: Invitation lifecycle, Mailpit capture, role administration, audit events, and concurrency behavior pass independently.

---

## Phase 6: Local Identity Infrastructure and Cross-Cutting Release Gates

**Purpose**: Make the complete identity test harness reproducible and document operational boundaries.

- [ ] T047 [P] Pin the official-ZITADEL-derived Compose services, dedicated PostgreSQL volume/network, Mailpit, healthchecks, and local-only ports in `identity/compose.identity.yml`.
- [ ] T048 [P] Document disposable local variables, first-start semantics, seed outputs, SMTP capture, and safe teardown in `identity/.env.identity.example` and `identity/README.md`.
- [ ] T049 [P] Implement a redacted local OIDC seed/setup script that creates the test organization/project/application without printing client secrets in `identity/scripts/seed-local-oidc.py`.
- [ ] T050 [P] Implement wait/readiness checks for ZITADEL discovery/JWKS, Mailpit API, API health, and Web health in `identity/scripts/wait-for-identity.sh` and `tests/integration/test_identity_stack_health.py`.
- [ ] T051 Run and record the full API testing skill workflow, including Ruff, Pyright, unit/API/integration tests, Alembic, OpenAPI, pip-audit, secret scan, Compose health, and memory sample in `specs/002-identity-households/quickstart.md`.
- [ ] T052 [P] Add a local warm-JWKS p95 benchmark and timeout/rotation measurement in `tests/performance/test_identity_latency.py`, then record the observed baseline and threshold in `specs/002-identity-households/quickstart.md`.
- [ ] T053 Run the local identity testing skill and record issuer/client/audience, JWKS, token/cookie boundaries, tenant isolation, logout/refresh, Mailpit assertions, health, skipped flows, and cleanup in `specs/002-identity-households/quickstart.md`.
- [ ] T054 [P] Review and update `AGENTS.md`, `.devin/skills/uribap-api-testing/SKILL.md`, and `.devin/skills/uribap-local-identity-testing/SKILL.md` only if the feature introduces a durable identity command or boundary not already documented.
- [ ] T055 Complete final read-only Spec Kit analysis and convergence; record results in `specs/002-identity-households/analyze.md`, `specs/002-identity-households/converge.md`, and `tasks.md` before closing the feature.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** has no feature-code dependency and may run in parallel.
- **Phase 2** depends on Phase 1 and blocks all user stories.
- **US1 (Phase 3)** depends on Phase 2.
- **US2 (Phase 4)** depends on US1 identity provisioning and Phase 2.
- **US3 (Phase 5)** depends on US1 and US2 membership/policy primitives.
- **Phase 6** depends on the relevant story implementation and is the final release gate.

### Parallel Opportunities

- T001–T005 can run in parallel in separate files.
- T006–T010 can run in parallel before foundational implementation.
- T019–T022, T028–T031, and T037–T040 can each run in parallel.
- T011/T012/T014–T018 can run in parallel after test scaffolds, provided shared model files do not overlap.
- T047–T050 can run in parallel after API/Web ports and contract values are agreed.

### MVP Scope

MVP is Phase 1 + Phase 2 + User Story 1 (T001–T027): a protected API that validates local OIDC, provisions identities, and returns safe current-user data. Household creation and invitation collaboration follow as independently testable increments.

### Notes

- Every task includes a file path and uses the required checkbox/ID format.
- Tests must be written and observed failing before their implementation task.
- No task may log secrets, use production identity, send real mail, or run destructive volume/database cleanup.

---

## Phase 7: Convergence (Remaining Work)

- [ ] T056 [P] Add deterministic API contract/error tests for every household and invitation route, including `401`, `403`, `404`, `409`, `If-Match`, and idempotency behavior in `tests/api/test_household_routes.py`, `tests/api/test_invitation_routes.py`, and `tests/api/test_identity_errors.py`. (FR-006, FR-008, FR-009, FR-012; partial)
- [ ] T057 [P] Complete audit/redaction assertions for Authorization headers, cookies, raw invitation tokens, SMTP values, and rejected membership mutations in `tests/unit/test_logging_redaction.py` and `tests/integration/test_audit_events.py`. (FR-011, FR-012; missing)
- [ ] T058 [P] Make `identity/scripts/seed-local-oidc.py` create/reuse the local project and PKCE application with an authorized disposable Admin API token, write only ignored env output, and add a safe repeatability test in `tests/integration/test_local_zitadel.py`. (FR-014; partial)
- [ ] T059 [P] Add live local identity tests for refresh, logout, invitation acceptance by a second synthetic user, and cross-household denial in `tests/integration/test_local_zitadel.py` and `tests/integration/test_tenant_isolation.py`. (FR-001, FR-010, FR-016; missing)
- [ ] T060 [P] Implement and run the warm-JWKS p95 benchmark, record p95/timeout/key-rotation evidence, and remove the placeholder skip from `tests/performance/test_identity_latency.py`. (SC-008; partial)
- [ ] T061 Run the complete `/uribap-api-testing` and `/uribap-local-identity-testing` workflows, including Compose smoke, `pip-audit`, secret scan, Docker stats, Mailpit assertions, and quickstart evidence in `specs/002-identity-households/quickstart.md`. (SC-006, SC-009; partial)
- [ ] T062 Re-run read-only Spec Kit analysis and update `specs/002-identity-households/analyze.md` and `converge.md`; only then mark this feature converged. (Constitution workflow; missing)

## Deployment Readiness Amendment

- [x] T063 Write failing deterministic tests in `tests/unit/infrastructure/test_userinfo.py`, `test_jwt_validator.py`, `tests/unit/test_config.py`, and `tests/unit/test_oidc_seed.py` for FR-017–FR-020.
- [x] T064 Add optional trusted UserInfo configuration and async profile retrieval in `src/uribap_api/config.py`, `infrastructure/identity/userinfo.py`, and `jwt_validator.py`; validate JWT/scopes first and bind subjects before provisioning.
- [x] T065 Correct the JWT seed/profile configuration and credential-file permissions in `identity/scripts/seed-local-oidc.py`; update `.env.example`, `identity/README.md`, and `docs/operations/coolify.md` without production secrets or real email delivery.
- [ ] T066 Run focused regression/static checks followed by the final repository and local-identity checks; record actual results and remaining gaps in existing quickstart/convergence artifacts.
- [ ] T067 Review the complete diff for credential leakage, cross-provider requests, verification escalation, tenant isolation, and contract compatibility; publish the bounded authentication PR without claiming older incomplete tasks are complete.
