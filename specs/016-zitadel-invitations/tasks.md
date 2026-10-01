# Tasks — 016 ZITADEL household invitations

## Phase 1: Specification and design

- [x] T001 Complete the feature spec, quality checklist, implementation plan, analysis gate, and quickstart.
- [x] T002 Define delivery response and pending-invitation contracts in the plan; confirm existing records support the flow without a migration.

## Phase 2: ZITADEL directory and settings

- [x] T003 Add settings validation tests for paired credentials, enabled state, issuer fallback, URL normalization, derived template, and production HTTPS.
- [x] T004 Add MockTransport unit tests for exact lookup, user creation/profile splitting, invite-code request, authentication, timeout/error mapping, and secret-safe exceptions.
- [x] T005 Implement validated ZITADEL settings and `.env.example` variables.
- [x] T006 Implement `ZitadelUserDirectory` and the overridable `get_user_directory` dependency.

## Phase 3: Invitation creation and delivery (P1)

- [x] T007 Add schema tests and implement optional normalized `display_name` and `InvitationCreatedResponse`.
- [x] T008 Add outbox suppression support and route tests for new identity, existing identity, directory failure, and SMTP fallback.
- [x] T009 Implement delivery branching after invitation persistence; do not call SMTP in directory mode.
- [x] T010 Verify directory failures preserve the invitation and return HTTP 202 with a safe failure status.

## Phase 4: In-app discovery and acceptance (P1)

- [x] T011 Add service tests for verified-email pending filtering, expiry, household/inviter presentation, and ID acceptance privacy.
- [x] T012 Extract shared locked-row acceptance logic and use it from token and by-ID service flows.
- [x] T013 Add authenticated `GET /me/invitations` and `POST /me/invitations/{invitation_id}/accept` routes.
- [x] T014 Extend authentication, authorization, and PostgreSQL integration coverage; verify token acceptance side effects remain identical.

## Phase 5: Deployment guidance and convergence

- [x] T015 Document Coolify variables, ZITADEL service-account setup, ZITADEL SMTP ownership, and application SMTP fallback.
- [x] T016 Regenerate and check `openapi/openapi.json`; confirm `uv run alembic check` detects no migration.
- [x] T017 Run all verification commands from `plan.md`, record results in `converge.md`, then commit and push the API branch.

## Review follow-up

- [x] T018 Scope ZITADEL user lookup to the configured organization.
- [x] T019 Keep invitation outbox rows non-claimable until route delivery completes.
- [x] T020 Retry failed pending invitations without creating duplicate invitation events or ZITADEL users.
- [x] T021 Run focused review regression tests and record the result in `converge.md`.
