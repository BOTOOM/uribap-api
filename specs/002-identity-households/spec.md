# Feature Specification: Identity and Households

**Feature Branch**: `002-identity-households`

**Created**: 2026-09-10

**Status**: Implementation in progress

**Input**: User description: "Implement the next Uribap phase with provider-neutral OIDC identity, ZITADEL local development, households, memberships, roles, invitations, tenant isolation, and complete tests."

## User Scenarios & Testing

### User Story 1 - Sign in and establish an Uribap identity (Priority: P1)

As a person who signs in through the configured identity provider, I want Uribap to recognize my provider identity and establish an internal user record so that protected API operations can be performed without Uribap storing a password.

**Why this priority**: Every household operation depends on a trustworthy, provider-validated identity boundary.

**Independent Test**: A disposable local ZITADEL user obtains an OIDC token, the API validates it against the local issuer and JWKS, and a repeated authenticated request resolves to the same internal user and identity without creating duplicates.

**Acceptance Scenarios**:

1. **Given** a valid token signed by the configured issuer with the required issuer, audience, expiry, subject, and scope claims, **When** the caller requests the current-user resource, **Then** the API returns the internal user profile and memberships.
2. **Given** a token with an invalid signature, issuer, audience, expiry, or required scope, **When** the caller requests a protected resource, **Then** the API returns a redacted `401` or `403` Problem Details response without logging the token.
3. **Given** the same `(issuer, subject)` identity is presented repeatedly, **When** authenticated requests are processed, **Then** exactly one linked identity and one internal user are retained.
4. **Given** the local identity stack has no external SMTP provider, **When** a basic OIDC login is performed, **Then** login, callback, token validation, and logout remain testable without real email delivery.

---

### User Story 2 - Create and operate a household (Priority: P1)

As an authenticated person, I want to create a household and manage its basic settings so that all future meal, inventory, shopping, and preparation data can be scoped to the correct home.

**Why this priority**: The household is the tenant boundary for all Uribap domain data and must exist before downstream features are built.

**Independent Test**: An authenticated user creates a household, becomes its owner, reads its settings and membership list, and updates allowed settings while a second household remains inaccessible.

**Acceptance Scenarios**:

1. **Given** an authenticated user without a household, **When** the user creates a household with a name, locale, and timezone, **Then** the API creates the household, creates an owner membership, and returns stable identifiers.
2. **Given** an owner or admin, **When** they read household details and members, **Then** the response contains only data for that household and permitted member fields.
3. **Given** a member without administration rights, **When** they attempt to change household settings or roles, **Then** the API returns `403` and makes no change.
4. **Given** a household member requests a tenant-owned resource, **When** the resource belongs to another household, **Then** the API does not reveal whether that resource exists.
5. **Given** two concurrent attempts to change the same household settings, **When** one update has already changed the version, **Then** the stale update returns a documented conflict response and does not overwrite the newer state.

---

### User Story 3 - Invite and manage household members (Priority: P1)

As a household owner or administrator, I want to invite people, assign roles, and revoke access so that the household can be used by the right people without sharing credentials.

**Why this priority**: A two-person household is the initial target, but role-aware membership and invitations are required for correct multi-member behavior.

**Independent Test**: An owner creates an invitation, the local Mailpit inbox receives a synthetic message, the invited person accepts once, and role changes or revocation enforce authorization and tenant isolation.

**Acceptance Scenarios**:

1. **Given** an owner or admin and a valid email address, **When** an invitation is created, **Then** the API stores only a hashed one-time token, records expiry and inviter, and queues a notification without exposing the raw token in logs or API responses.
2. **Given** a pending invitation and an authenticated person whose verified email matches it, **When** the invitation is accepted, **Then** a membership is created with the requested allowed role and the invitation becomes consumed.
3. **Given** an expired, consumed, revoked, or mismatched invitation, **When** it is accepted, **Then** the API returns a safe `400`, `403`, or `409` response and does not create membership.
4. **Given** an owner, **When** the owner changes a member between `admin` and `member` or revokes access, **Then** subsequent requests enforce the new state immediately or after the documented token/session refresh boundary.
5. **Given** a member or admin attempts to remove the last owner or change ownership without the required owner rule, **When** the mutation is submitted, **Then** the API rejects it and preserves at least one valid owner.
6. **Given** a complete local email-flow test, **When** verification, reset, or invitation messages are generated, **Then** assertions are made against Mailpit and no external SMTP service is contacted.

---

### Edge Cases

- A provider rotates signing keys while the API has a cached JWKS document.
- A token is validly signed but has the wrong issuer, audience, algorithm, scope, or tenant claims.
- Two requests concurrently provision the same provider identity or accept the same invitation.
- A user changes email at the identity provider after an invitation was issued.
- The invitation target already has a membership, belongs to another household, or has a pending invitation.
- An owner attempts to leave, delete, or demote the last owner.
- A household name is empty, too long, or contains unsupported control characters.
- Mailpit, ZITADEL, JWKS, or PostgreSQL is unavailable during a local test.
- A client retries a mutation after receiving a timeout or connection reset.
- A request is authenticated but has no membership in the requested household.

## Requirements

### Functional Requirements

- **FR-001**: The API MUST validate OIDC access tokens using the configured issuer's JWKS and MUST verify signature, approved algorithm, issuer, audience, expiry, not-before when present, subject, and required scopes.
- **FR-002**: The API MUST identify an internal user by a stable provider-neutral user record and MUST link provider identities using the unique `(issuer, subject)` pair.
- **FR-003**: Identity provisioning MUST be idempotent under retries and concurrent requests and MUST never store a user password or provider client secret.
- **FR-004**: The API MUST expose an authenticated current-user resource containing safe profile data and the caller's active household memberships.
- **FR-005**: An authenticated user MUST be able to create a household with a name, locale, timezone, and owner membership.
- **FR-006**: Every household-owned read and mutation MUST require an active membership in that household and MUST enforce the roles `owner`, `admin`, and `member`.
- **FR-007**: The API MUST enforce role permissions: owners can manage ownership and all household settings, admins can manage ordinary members and settings allowed by policy, and members can access ordinary household data without administration rights.
- **FR-008**: Household settings and membership mutations MUST use optimistic concurrency and MUST return a documented conflict when the client version is stale.
- **FR-009**: Owners and permitted admins MUST be able to create, list, revoke, and resend invitations with expiration, one-time consumption, role restrictions, and normalized email handling.
- **FR-010**: Invitation acceptance MUST verify the authenticated user's verified email or documented identity match, consume the invitation atomically, and be safe under retries and concurrent acceptance attempts.
- **FR-011**: Invitation and membership changes MUST produce structured audit events containing actor, household, action, target, request correlation ID, and timestamp without tokens or secrets.
- **FR-012**: Authentication, authorization, validation, not-found, conflict, and dependency failures MUST use the existing Problem Details contract with stable machine-readable codes and safe details.
- **FR-013**: The API MUST publish all identity and household resources, permissions, errors, pagination, idempotency, and concurrency headers in the canonical OpenAPI contract.
- **FR-014**: Local development and CI-like identity tests MUST use a dedicated ZITADEL PostgreSQL volume and Mailpit; Brevo and real SMTP credentials MUST NOT be required or used locally.
- **FR-015**: The local identity Compose stack MUST expose documented liveness/readiness checks for PostgreSQL, ZITADEL, Mailpit, the API, and the Web boundary; the Web boundary may satisfy this through its own public health route or Docker healthcheck, documented in the Web feature contract.
- **FR-016**: Tenant isolation tests MUST demonstrate that a user cannot read or mutate another household's members, invitations, settings, or future tenant-owned resources.

### Key Entities

- **AppUser**: Internal Uribap user record with stable ID, safe display profile, normalized verified email when available, status, timestamps, and audit metadata.
- **UserIdentity**: Provider link identified uniquely by issuer and subject, with provider name, last-seen metadata, and no provider secret.
- **Household**: Tenant boundary with name, locale, timezone, lifecycle status, optimistic version, and timestamps.
- **HouseholdMember**: Association between an internal user and household with role, status, membership timestamps, and version/audit metadata.
- **HouseholdInvitation**: One-time invitation record with normalized email, hashed token, requested role, expiry, state, inviter, consumption metadata, and household reference.
- **AuditEvent**: Append-only security and membership event with actor, household, action, target, correlation ID, timestamp, and redacted metadata.
- **EmailOutboxEntry**: Durable, idempotent notification intent for verification/reset/invitation messages; it contains no plaintext secrets beyond the minimum delivery payload policy.

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of protected API acceptance tests reject invalid signature, issuer, audience, expiry, scope, and tenant membership cases without exposing tokens or secrets.
- **SC-002**: Repeating the same identity provisioning request 100 times concurrently results in exactly one internal user and one `(issuer, subject)` identity link.
- **SC-003**: A new authenticated user can create a household and receive an owner membership in one successful API flow with no manual database edits.
- **SC-004**: 100% of cross-household read and mutation tests return the documented safe denial behavior and expose no protected resource data.
- **SC-005**: 100% of invitation acceptance tests prove one-time consumption, expiry, email matching, role restrictions, retry idempotency, and concurrent acceptance safety.
- **SC-006**: The local complete identity test run passes with ZITADEL, its dedicated PostgreSQL, Mailpit, API, and Web available, and sends zero messages to an external SMTP endpoint.
- **SC-007**: The generated API contract check passes deterministically and covers all identity, household, membership, invitation, error, pagination, idempotency, and concurrency behavior.
- **SC-008**: Protected API requests complete within 500ms p95 in the local foundation profile when JWKS is warm and PostgreSQL is healthy; cold JWKS fetches have a documented timeout and failure behavior.
- **SC-009**: Audit events exist for 100% of successful and rejected membership/invitation security mutations without storing raw invitation tokens or authorization headers.

## Assumptions

- ZITADEL is the selected provider for the first deployment, but the API identity boundary remains provider-neutral and is configured by issuer, audience, JWKS, and claims settings.
- The initial household target is two people, while the schema and authorization model support any practical household size.
- A verified email claim is required for invitation acceptance; the local test identity provider can issue synthetic verified addresses.
- The API remains a modular monolith with direct, reviewed SQLAlchemy/Alembic persistence and no queue or external identity microservice.
- Email delivery is represented through a local outbox/notification boundary; Mailpit is the only SMTP endpoint in local and CI-like identity tests.
- Production Brevo configuration is documented separately and is not part of local feature acceptance.
- Password storage, social-provider credential management, nutrition, recipes, inventory, forecasting, shopping, and preparation calculations remain outside this feature.
