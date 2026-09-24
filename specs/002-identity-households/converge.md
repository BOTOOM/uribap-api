# Convergence Report: Identity and Households

**Date**: 2026-09-10
**Status**: In progress — remaining tasks appended to `tasks.md`

## Verified implementation

- OIDC issuer/audience/signature/expiry validation with asynchronous JWKS cache is implemented and tested at the claim/unit boundary.
- Internal user/identity provisioning, household/membership models, Alembic migration, `/me`, household routes, invitation routes, audit/outbox boundary, local ZITADEL Compose, Mailpit, health checks, and OpenAPI are implemented.
- PostgreSQL migration and tenant-isolation/invitation integration tests pass.
- Local ZITADEL discovery/JWKS, real PKCE/Auth.js login, API JWT validation, onboarding, BFF household creation, and Mailpit invitation delivery were exercised locally.

## Remaining gaps

1. Local seed automation needs an Admin API token with project/application permissions; the bootstrap login PAT intentionally returns 403. The app was created through the local admin Console for validation, but the reusable seed must be rerun with an authorized disposable token.
2. Authorization error/contract tests do not yet cover every household/invitation route and concurrency/idempotency header path.
3. Full local identity acceptance still needs refresh rotation, federated logout, invitation acceptance by a second synthetic user, and explicit cross-household denial against live JWTs.
4. JWKS p95 benchmark, full resource sample, Compose smoke, and the complete reusable identity skill report remain pending.
5. Secret-redaction/audit assertions and a dedicated API identity integration test file need completion.

The feature remains `Ready for implementation`/in progress and must not be considered converged until the appended tasks pass.

## Deployment Readiness Amendment — evidence on 2026-09-24

T063–T065 have focused regression and static evidence: URL validation handles explicit/default ports including rejection of UserInfo port `0`; UserInfo email normalization rejects invalid provider addresses with redacted 503s; JWT/subject binding, seed JWT/profile settings, empty `OIDC_REQUIRED_SCOPES` for stock ZITADEL 4.16, and `0600` seed output are covered by synthetic tests. The focused config/UserInfo suite passed 41 tests, the seed/JWT compatibility suite passed 11 tests, and full Ruff, Pyright, unit/API/integration, OpenAPI, and dependency-audit gates passed as recorded in `quickstart.md`.

T068 resolves the existing `mcp_token.token_hash` metadata mismatch by declaring the migration's named `UniqueConstraint` alongside the existing unique index; the metadata regression and `alembic check` pass on the dedicated DB without DDL or migration changes. T069 adds that check to API CI after migrations. The stock ZITADEL 4.16 scope compatibility tests and local Docker UserInfo transport probe pass; a valid user `/me` profile assertion remains NOT RUN. The broad unit/API/integration suite is recorded from before the bounded follow-ups and was not rerun. T066 remains open because live local OIDC acceptance is pending and two integration tests were skipped. Historical tasks remain unchanged. T067 review/PR remains with the lead.
