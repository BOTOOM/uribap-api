# Tasks: Household Invitation Management

**Input**: Design documents from `/specs/021-invitation-management/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi-delta.md

## Phase 1: Foundational

- [ ] T001 Extend `InvitationResponse` in `src/uribap_api/api/schemas.py` with `effective_status` (pending|expired|accepted|revoked) and `delivery` (sent|failed|existing_account|pending|null).
- [ ] T002 In `src/uribap_api/application/invitation_service.py`, return the delivery outbox row alongside each invitation in `list_invitations` (batched select by `dedupe_key`), and derive `effective_status` in `invitation_response` (pending + `expires_at <= now` → `expired`).

## Phase 3: User Story 1 — list with state + delivery (P1)

- [ ] T003 [US1] Integration test: seeded invitations in each state + outbox variants → `GET /households/{id}/invitations` reports correct `effective_status`/`delivery`; non-owner gets 403 (`tests/integration/test_invitation_flows.py`).
- [ ] T004 [US1] Wire the enriched mapping in `src/uribap_api/api/invitations.py` list route.

## Phase 4: User Story 2 — resend expired/failed (P2)

- [ ] T005 [US2] Integration test: resend an expired invitation via `POST` → 202, rotated `token_hash`, fresh expiry; resend a delivery-FAILED one → retry; resend valid pending → 409 (partially covered by PRs #158/#159 — fill gaps).
- [ ] T006 [US2] Verify no code change needed beyond list enrichment (renewal path already in `create_invitation`); adjust only if a gap appears.

## Phase 5: User Story 3 — revoke (P3)

- [ ] T007 [US3] Integration test: revoke pending → accept afterwards fails; revoke non-pending → error.

## Phase 6: Contract + quality gates

- [ ] T008 Regenerate `openapi/uribap-api.openapi.json` and confirm it matches contracts/openapi-delta.md.
- [ ] T009 Full suite: `uv run pytest tests/integration/test_invitation_flows.py -q`, `uv run ruff check`, `uv run ruff format --check`.

## Phase 7: Web counterpart (separate repo)

- [ ] T010 uribap-web: invitations panel in household settings — list with email/role/state/delivery/expiry, Resend (expired or failed) and Revoke (pending) actions, regenerate pinned contract.
