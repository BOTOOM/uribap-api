# Implementation Plan: Household Invitation Management

**Branch**: `devin-invitation-management` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/021-invitation-management/spec.md`

## Summary

Give household owners/admins visibility and control over invitations. The API already lists invitations (`GET /households/{id}/invitations`), creates/renews them (`POST`), and revokes them (`DELETE`). Missing: the delivery outcome per invitation (email outbox status) and an effective-state derivation (pending vs expired) in the contract, plus a resend action the web client can call for expired/failed invitations — which reuses the existing renewal path in `create_invitation`. The uribap-web counterpart (separate repo/PR) renders the list with resend/revoke actions in household settings.

## Technical Context

**Language/Version**: Python 3.14, UV-managed

**Primary Dependencies**: FastAPI, SQLAlchemy 2, Pydantic, Alembic

**Storage**: PostgreSQL (`household_invitations`, `email_outbox`)

**Testing**: pytest (unit/domain + integration with real PostgreSQL via compose `db`)

**Target Platform**: Linux server (Coolify deploy)

**Project Type**: web-service (FastAPI modular monolith)

**Performance Goals**: n/a — owner-facing admin view, low volume

**Constraints**: single worker, small pool; no new infrastructure (Principle VI)

**Scale/Scope**: invitations per household are O(dozens); list capped at 100 (existing limit)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Domain correctness**: no inventory/quantity impact — N/A. PASS.
- **II. Deterministic domain**: effective state (pending vs expired) is a pure derivation in `invitation_service`/schema mapping; no framework-bound calculation. PASS.
- **III. Test-first**: integration tests for list effective-state, resend authorization/state gating, and delivery outcome exposure land with the implementation. PASS.
- **IV. Tenant isolation**: list/resend/revoke all behind `require_household_membership(OWNER, ADMIN)`; no secrets in responses — delivery outcome is an enum, raw tokens never returned. PASS.
- **V. Contract-first**: `InvitationResponse` gains `delivery` + derived `effective_status`; regenerate pinned OpenAPI for the web client (non-breaking additive change). PASS.
- **VI. Resource-aware**: reuses existing endpoints, tables and outbox; no new infra. PASS.
- **VII. Auditable operations**: no migration needed (all fields exist); resend reuses the audited renewal path. PASS.

## Project Structure

### Documentation (this feature)

```text
specs/021-invitation-management/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/uribap_api/
├── api/invitations.py            # GET list (add delivery/effective_status), resend route if needed
├── api/schemas.py                # InvitationResponse fields
└── application/invitation_service.py  # list_invitations with outbox join, resend_invitation

tests/
└── integration/test_invitation_flows.py  # new cases
```

**Structure Decision**: extend the existing invitations module; no new modules. The web-side work (settings UI) lives in `BOTOOM/uribap-web` consuming the regenerated contract.

## Model Policy

- **Primary**: `gpt-5-6-luna-max` (domain/architecture)
- **Implementation**: `gpt-5-6-sol-high`
- **Security/transaction review**: `gpt-5-6-terra-high`
- **Subagent/bounded fixes**: `swe-2-high`
- **Escalation**: cross-repo contract drift → `kimi-k3-max`

## Complexity Tracking

> No constitution violations; nothing to justify.
