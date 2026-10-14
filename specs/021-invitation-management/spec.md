# Feature Specification: Household Invitation Management

**Feature Branch**: `devin-invitation-management`

**Created**: 2026-10-14

**Status**: Draft

**Input**: User description: "yo debería de poder ver a quienes tengo en enviado y pendientes y quienes fallaron para reenviarles la invitación" — the household owner must be able to see invitations that are sent/pending and the ones that failed, so they can resend invitations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Owner reviews every invitation's state (Priority: P1)

As the owner (or admin) of a household, I open the household settings and see a list of every invitation ever sent for that household: the invited email, requested role, current state, delivery outcome, when it was created and when it expires.

**Why this priority**: Today an owner has no visibility at all — they can't tell whether an invitation was sent, is still pending, expired, was accepted, was revoked, or failed to deliver. This caused a real incident: an invitee registered but couldn't join, and the owner could not tell why. Visibility is the foundation for every other action in this feature.

**Independent Test**: Create a household, send invitations covering the possible outcomes (accepted, still pending, expired, revoked, failed delivery, invitee already had an account), open the invitations view as the owner and verify each row shows the correct state without touching any other feature.

**Acceptance Scenarios**:

1. **Given** a household with invitations in several states, **When** the owner opens the invitations list, **Then** every invitation is shown with its invited email, role, effective state, delivery outcome and expiry time.
2. **Given** an invitation whose expiry has passed but which was never accepted or revoked, **When** the owner views the list, **Then** it is presented as expired (not as still usable).
3. **Given** a user who is not an owner or admin of the household, **When** they try to view the invitations list, **Then** they are denied access.
4. **Given** an invitation that failed to deliver, **When** the owner views the list, **Then** the failed delivery is clearly distinguishable from a delivered one.

---

### User Story 2 - Owner resends an invitation (Priority: P2)

As the owner, from the same list I resend an invitation that failed to deliver or that expired, so the invitee can join without me retyping their email.

**Why this priority**: Once the owner can see failed or expired invitations, the natural next step is fixing them. Resending from the list turns the dead-end state (expired or delivery-failed) into a recoverable one in one action. Without this, visibility alone still forces the owner to remember the email and re-invite manually.

**Independent Test**: Take a household with an expired invitation and one with a failed delivery, resend each from the list, and verify a usable invitation results while already-accepted or still-valid invitations offer no resend action.

**Acceptance Scenarios**:

1. **Given** an invitation that expired without being accepted, **When** the owner resends it, **Then** the invitee can accept the renewed invitation and the owner sees a confirmation of the new delivery outcome.
2. **Given** an invitation whose delivery failed, **When** the owner resends it, **Then** the system retries delivery and reports the result.
3. **Given** an invitation that is still valid and pending, **When** the owner views the list, **Then** no resend action is offered for it (it can still be accepted as-is).
4. **Given** an invitation that was already accepted or revoked, **When** the owner views the list, **Then** no resend action is offered for it.

---

### User Story 3 - Owner revokes a pending invitation (Priority: P3)

As the owner, I revoke a pending invitation that should no longer be usable — for example after inviting the wrong address or when an invitee should not join anymore.

**Why this priority**: Revocation already exists in the product; it only needs to be reachable from the same list so the owner manages invitations in one place. It is lower priority because it is a corrective action, not the main loop that failed in the incident.

**Independent Test**: Create a pending invitation, revoke it from the list, and verify the invitee can no longer accept it while other invitations are unaffected.

**Acceptance Scenarios**:

1. **Given** a pending invitation, **When** the owner revokes it, **Then** the invitation can no longer be accepted and the list shows its revoked state.
2. **Given** an invitation that is no longer pending, **When** the owner views the list, **Then** no revoke action is offered for it.

---

### Edge Cases

- An invitation whose expiry passed but was never resolved must be shown as expired, never as valid-and-pending.
- Resending an invitation whose invitee already has an account produces no email delivery: the invitee accepts the renewed invitation from their own pending-invitations view inside the app.
- An invitee who never receives the invitation (delivery suppressed or failed) must not be able to guess or reuse an old token: resending issues a new token and the previous one stops working.
- Repeated resends are idempotent in effect: each resend renews the same invitation rather than creating duplicates for the same email and household.
- The list is ordered so actionable items (failed, expired) are easy to find.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST let an owner or admin list all invitations of their household, each with invited email, requested role, effective state, delivery outcome, creation time and expiry time.
- **FR-002**: The effective state MUST distinguish at least: valid-and-pending, expired (expiry passed, still unresolved), accepted, revoked, and failed delivery.
- **FR-003**: Only owners and admins of the household MUST be able to view invitations and act on them.
- **FR-004**: Owners/admins MUST be able to resend an invitation that is expired or whose delivery failed, in one action, without re-entering the email.
- **FR-005**: Resending MUST produce a usable invitation (new token, fresh expiry) and MUST invalidate the previous token.
- **FR-006**: Resending MUST NOT create a duplicate invitation for the same email and household.
- **FR-007**: When the invitee already has an account, resending MUST make the renewed invitation visible to that invitee inside the application (no email delivery required).
- **FR-008**: Resending MUST report the resulting delivery outcome to the owner (sent, failed, or invitee already has an account).
- **FR-009**: Resend and revoke actions MUST NOT be offered for invitations in states where they cannot take effect (accepted, revoked, still-valid pending for resend; non-pending for revoke).
- **FR-010**: Owners/admins MUST be able to revoke a pending invitation, after which it can no longer be accepted.

### Key Entities

- **Household Invitation**: An invite issued by an owner/admin for a household. Carries invited email, requested role, lifecycle state (pending → accepted / expired-by-time / revoked), token validity and expiry.
- **Delivery Record**: The recorded outcome of attempting to deliver an invitation to its channel (sent, failed, suppressed because the invitee already has an account). One per invitation, updated on each resend.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An owner can answer "what happened to invitation X" for 100% of invitations of their household without leaving the household settings — zero invitations in an ambiguous or hidden state.
- **SC-002**: An owner can recover a failed or expired invitation in at most 2 actions (open list, resend), without re-entering the invited email.
- **SC-003**: After a resend, 100% of invitations are either freshly usable by the invitee or report a concrete delivery outcome (never silent).
- **SC-004**: An expired or failed invitation for an already-registered invitee becomes joinable end-to-end (accept to active member) in under 2 minutes from the owner's resend action.

## Assumptions

- "Owner" means household members with the owner or admin role; other members cannot see or manage invitations.
- Delivery-failed and expired invitations are the actionable states; still-valid pending and already-resolved invitations are informational only.
- An invitation that expired while still pending is presented as expired even if no background job ever updated its stored state (the effective state is derived).
- Resending reuses the same invitation (renewed token and expiry) rather than issuing a second invitation row for the same email.
- The invitations list lives inside the existing household settings area alongside member management; no new navigation surface is required.
- The invitee-side experience (viewing and accepting a pending invitation after sign-in) already exists and is unchanged.
