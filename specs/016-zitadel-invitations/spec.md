# Feature Specification: ZITADEL Household Invitations

**Feature Branch**: `016-zitadel-invitations`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: Connect household invitations to ZITADEL and let signed-in invitees find and accept invitations for their verified email.

## User Scenarios & Testing

### User Story 1 - Invite a person to a household (Priority: P1)

A household owner invites someone by email and can optionally provide their name. If the person does not yet have an identity account, they receive an account-setup invitation. If they already have an account, no extra email is sent and the invitation is available after they sign in.

**Why this priority**: Household owners need a dependable path to invite both new and existing users.

**Independent Test**: Submit invitations for a new identity, an existing identity, a failed identity-provider request, and an unconfigured identity provider; verify the invitation remains available and the owner receives the matching delivery outcome.

**Acceptance Scenarios**:

1. **Given** an owner invites an email with no identity account, **When** the invitation is created, **Then** the person receives an account-setup invitation and the owner is told that the email was requested.
2. **Given** an owner invites an email with an existing identity account, **When** the invitation is created, **Then** no email is sent and the owner is told the person can accept after signing in.
3. **Given** identity-invitation delivery fails, **When** the owner submits the invitation, **Then** the invitation remains persisted and the response reports delivery failure.
4. **Given** identity invitations are not configured, **When** the owner submits the invitation, **Then** the existing email-delivery path is used and its outcome is reported.

---

### User Story 2 - Find and accept household invitations after sign-in (Priority: P1)

A person who signs in with a verified email can see pending, unexpired invitations addressed to that email and accept one without copying an invitation token.

**Why this priority**: People with existing accounts need a direct in-app path to join without receiving a separate invitation email.

**Independent Test**: Sign in as a verified user with pending invitations and accept one by its invitation entry; verify the invitation is accepted and the requested household membership becomes active.

**Acceptance Scenarios**:

1. **Given** a verified user has pending, unexpired invitations for their email, **When** they view their invitations, **Then** they see the household, requested role, inviter, and expiry.
2. **Given** a verified user selects one of their pending invitations, **When** they accept it, **Then** the invitation is accepted and membership is activated.
3. **Given** an invitation is addressed to another email, **When** a user requests or accepts it, **Then** it is not disclosed and the action returns not found.
4. **Given** the user's email is absent or unverified, **When** they view or accept invitations, **Then** listing returns no invitations and acceptance is forbidden.
5. **Given** an invitation is expired or the user is already an active member, **When** they accept it, **Then** the same error behavior as token-based acceptance is preserved.

---

### User Story 3 - Preserve secure token-based acceptance (Priority: P2)

A person who opens an invitation link while signed out can sign in and return to the same invitation, while the existing token-based acceptance flow continues to behave as before.

**Why this priority**: New invitees still need the original link-based route, and losing its token during sign-in prevents them from joining.

**Independent Test**: Exercise the existing token acceptance path before and after sign-in and verify the token remains available and the same invitation is accepted.

**Acceptance Scenarios**:

1. **Given** a signed-out person opens a valid invitation link, **When** they are redirected to sign in, **Then** returning to the application preserves the invitation token.
2. **Given** a verified user accepts an invitation by token, **When** the request succeeds, **Then** its membership, audit, and event effects remain unchanged.

## Edge Cases

- Identity-provider timeouts, non-success responses, and transport failures must not erase the persisted household invitation.
- Existing identities must not receive a second invitation email from the application.
- Email matching must be case-insensitive and limited to the signed-in user's normalized verified email.
- An invitation that expires between listing and acceptance must be rejected at acceptance time.
- Invitation tokens, service credentials, email addresses, and response bodies must not appear in delivery-error logs or exception text.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST let an owner provide an optional display name when inviting an email address.
- **FR-002**: The system MUST report whether a created invitation used an identity-provider invitation, targeted an existing account, used application email, or could not be delivered.
- **FR-003**: For an email without an identity account, the system MUST create the account and request an account-setup email from the identity provider.
- **FR-004**: For an email with an existing identity account, the system MUST avoid sending another email and make the pending household invitation available after sign-in.
- **FR-005**: A delivery failure MUST leave the household invitation persisted and report failure without exposing sensitive details.
- **FR-006**: When identity-provider invitations are not configured, the existing application email path MUST remain available.
- **FR-007**: A signed-in user with a verified email MUST be able to list only their own pending, unexpired invitations.
- **FR-008**: A verified user MUST be able to accept an invitation addressed to their email without providing its token.
- **FR-009**: The system MUST conceal invitations addressed to another email and MUST preserve existing expiry, membership, and authorization errors.
- **FR-010**: Token-based acceptance MUST retain its existing membership, audit, and event behavior.
### Key Entities

- **Household invitation**: A pending request to join a household, tied to a normalized email, requested role, expiry, inviter, and delivery intent.
- **Identity account**: A person’s sign-in identity, including the email address whose verification authorizes invitation discovery and acceptance.
- **Household membership**: The active relationship created when an eligible person accepts an invitation.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every invitation request gives the owner one clear status: account-invitation email requested, existing account, application email sent, or delivery failed.
- **SC-002**: A verified invitee can discover and accept an invitation addressed to their email without copying a token.
- **SC-003**: Requests for invitations belonging to another email disclose no invitation details.
- **SC-004**: Identity-provider delivery failures leave the invitation available for later in-app acceptance.
- **SC-005**: Existing token acceptance retains its prior membership and audit/event effects.

## Assumptions

- The identity provider supports exact, case-insensitive email lookup, account creation, and invitation-code email delivery.
- Identity-invitation credentials and organization configuration are supplied by deployment configuration; application email remains the fallback when the integration is disabled.
- The invited person's identity email must be verified before invitation discovery or acceptance.
