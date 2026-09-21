# Traceability: Identity and Households

This matrix maps every functional requirement and buildable success criterion to implementation/test tasks. It is reviewed before implementation and again during convergence.

## Functional requirements

| Requirement | Tasks | Evidence target |
|---|---|---|
| FR-001 OIDC/JWKS validation | T006, T014, T019, T022 | Pure claim/JWKS tests and local ZITADEL validation |
| FR-002 provider-neutral internal identity | T011, T012, T021, T023 | `(issuer, subject)` model and provisioning tests |
| FR-003 idempotent provisioning/no secrets | T006, T009, T018, T021, T023, T026 | Concurrent retry and redaction tests |
| FR-004 current-user resource | T020, T023–T025 | `/me` contract/API tests |
| FR-005 household creation | T028–T034 | Create-household API/integration tests |
| FR-006 active membership authorization | T007, T015, T029–T031, T034 | Role and tenant dependency tests |
| FR-007 owner/admin/member policy | T007, T029, T033–T035 | Pure policy and route tests |
| FR-008 optimistic concurrency | T028–T030, T035–T036 | `If-Match`, version, and conflict tests |
| FR-009 invitation lifecycle | T037–T045 | Invitation contract/service/Mailpit tests |
| FR-010 atomic verified-email acceptance | T008, T038–T043 | Hash, email match, retry, and concurrency tests |
| FR-011 audit events | T009, T017–T018, T039, T045 | Append-only/redaction/audit assertions |
| FR-012 Problem Details errors | T010, T016, T020, T028, T037 | Stable error code contract tests |
| FR-013 canonical OpenAPI | T005, T027, T036, T046 | Export and snapshot checks |
| FR-014 local ZITADEL/PostgreSQL/Mailpit/no Brevo | T003, T022, T040, T047–T053 | Compose and local email assertions |
| FR-015 complete stack health | T047–T050, T053 | PostgreSQL/ZITADEL/Mailpit/API/Web health checks |
| FR-016 tenant isolation | T030–T031, T039, T053 | Two-user/two-household integration tests |

## Buildable success criteria

| Criterion | Tasks | Evidence target |
|---|---|---|
| SC-001 invalid token cases | T006, T019, T022 | 100% invalid-claim rejection matrix |
| SC-002 concurrent provisioning uniqueness | T021, T023 | 100 concurrent requests, one identity/user |
| SC-003 household onboarding API flow | T028, T033–T034 | No manual DB edit create flow |
| SC-004 cross-household denial | T030–T031 | Safe denial/no data leakage |
| SC-005 invitation lifecycle safety | T037–T040, T042–T043 | One-time/expiry/mismatch/concurrency evidence |
| SC-006 complete local identity stack | T047–T053 | No external SMTP, all local services ready |
| SC-007 deterministic OpenAPI | T027, T036, T046 | Snapshot export/check |
| SC-008 warm-JWKS p95/timeout | T014, T019, T022, T052 | Benchmark and recorded baseline |
| SC-009 security audit coverage | T017–T018, T039, T045 | Redacted audit event assertions |

## Cross-repository dependency

Web T003/T044 and Web identity tests depend on API T027/T036/T046 publishing the canonical OpenAPI snapshot and the local identity Compose stack being ready. API FR-015 accepts the Web health route or Docker healthcheck documented by the Web contract.
