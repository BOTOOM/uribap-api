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
