# Spec Kit Analysis: Identity and Households

**Feature**: `002-identity-households`
**Date**: 2026-09-10
**Mode**: Read-only artifact analysis before implementation
**Inputs**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `traceability.md`, `tasks.md`, API constitution, and `AGENTS.md`

## Verdict

**PASS — ready for implementation.** No critical or high-severity inconsistencies remain after the design corrections recorded before this analysis.

`converge` is intentionally a post-implementation phase in the required workflow (`... → analyze → implement → converge`). Its absence before implementation is expected; it will be produced after implementation and testing, not used to bypass this pre-code gate.

## Checks performed

| Check | Result | Evidence |
|---|---|---|
| Spec completeness | PASS | Three independently testable P1 stories, 16 FRs, 9 buildable SCs, edge cases, entities, assumptions |
| Plan alignment | PASS | OIDC/JWKS, persistence, tenant isolation, local Compose, Mailpit, OpenAPI, and resource constraints are represented |
| API contract coverage | PASS | `/me`, household, members, invitation, health identity, errors, versions, idempotency, and pagination are specified |
| Task format | PASS | 55 unique IDs, all checkbox tasks include concrete paths, no sample placeholders |
| FR/SC traceability | PASS | `traceability.md` maps all FR-001–FR-016 and SC-001–SC-009 to tasks |
| Constitution alignment | PASS | Secure identity, tenant membership authorization, test-first, contract-first, modular monolith, audit, and no-secret rules are preserved |
| Local identity boundary | PASS | Dedicated ZITADEL PostgreSQL, Mailpit-only SMTP, no Brevo/real credentials, safe teardown |
| API/Web boundary | PASS | API owns identity/household decisions; Web owns BFF/session/UI; Web contract depends on API snapshot explicitly |
| Invitation security | PASS | API atomic POST acceptance; Web GET form and separate POST BFF route; raw tokens never public |
| Open issues/placeholders | PASS | No `[NEEDS CLARIFICATION]`, `TODO`, template placeholders, or obsolete SWE references in feature artifacts |

## Resolved findings before analysis

1. Separated the Web invitation page (`GET /invitations/accept`) from the server BFF mutation (`POST /api/invitations/accept`) to avoid App Router route collision and token leakage.
2. Added `updateHousehold(id, input, version)` to the Web server API contract.
3. Added explicit API-to-Web OpenAPI snapshot dependency in Web tasks and traceability.
4. Added Web `/api/health` as the documented boundary health option and a Web health task.
5. Added API warm-JWKS p95 benchmark task for SC-008.
6. Clarified that `app_user.email` is a non-unique verified profile snapshot, not an identity key.
7. Added API/Web FR/SC traceability matrices.
8. Clarified that foundation `/health/live` and `/health/ready` remain distinct from the identity diagnostic endpoint.

## Remaining implementation decisions

These are planned implementation choices, not unresolved specification ambiguities:

- Exact mature dependency versions will be selected by the package managers and security gates.
- The official ZITADEL Compose files/version will be pinned during the implementation task and recorded in the local runbook.
- Auth.js provider/client registration values will be synthetic and local-only.
- `converge.md` will be written after code, tests, and quickstart validation assess the actual implementation.

## Metrics

- Functional requirements: 16; mapped: 16 (100%).
- Buildable success criteria: 9; mapped: 9 (100%).
- API tasks: 55; unique IDs: 55; format violations: 0 after path normalization.
- Critical findings: 0.
- High findings: 0.
- Medium/low observations: 0 blocking; remaining items are implementation-time evidence gates.

## Gate decision

Product code MAY begin only after this analysis artifact is committed with the feature specs. All implementation tasks remain unchecked until their tests and quickstart evidence pass.
