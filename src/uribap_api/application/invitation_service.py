from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.api.schemas import InvitationCreate
from uribap_api.application.audit_service import record_audit
from uribap_api.domain.identity.policies import (
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    create_invitation_token,
    hash_invitation_token,
    invitation_is_usable,
    normalize_email,
)
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.email.outbox import queue_email
from uribap_api.infrastructure.persistence.household_models import (
    EmailOutboxEntry,
    HouseholdInvitation,
    HouseholdMember,
    OutboxKind,
)
from uribap_api.infrastructure.persistence.identity_models import AppUser


def create_invitation(
    session: Session,
    *,
    household_id: UUID,
    inviter: HouseholdMember,
    payload: InvitationCreate,
    request_id: str,
) -> tuple[HouseholdInvitation, str, EmailOutboxEntry]:
    email = normalize_email(payload.email)
    existing_member = session.scalar(
        select(HouseholdMember)
        .join(AppUser, AppUser.id == HouseholdMember.user_id)
        .where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.status == MembershipStatus.ACTIVE,
            AppUser.email == email,
        )
    )
    if existing_member is not None:
        raise DomainError(
            "conflict", "Invitation conflict", "The email is already a household member.", 409
        )
    pending = session.scalar(
        select(HouseholdInvitation).where(
            HouseholdInvitation.household_id == household_id,
            HouseholdInvitation.invited_email == email,
            HouseholdInvitation.status == InvitationStatus.PENDING,
        )
    )
    if pending is not None:
        raise DomainError(
            "conflict", "Invitation conflict", "A pending invitation already exists.", 409
        )
    token = create_invitation_token()
    now = datetime.now(UTC)
    invitation = HouseholdInvitation(
        household_id=household_id,
        invited_email=email,
        token_hash=token.digest,
        requested_role=MembershipRole(payload.role),
        expires_at=now + timedelta(hours=payload.expires_in_hours),
        invited_by_user_id=inviter.user_id,
    )
    session.add(invitation)
    session.flush()
    outbox = queue_email(
        session,
        dedupe_key=f"household-invitation:{invitation.id}",
        kind=OutboxKind.HOUSEHOLD_INVITATION,
        recipient_email=email,
        template_data={"body": "You have been invited to join a Uribap household."},
    )
    record_audit(
        session,
        actor_user_id=inviter.user_id,
        household_id=household_id,
        action="invitation.created",
        request_id=request_id,
        target_type="invitation",
        target_id=invitation.id,
        metadata={"role": payload.role},
    )
    session.commit()
    session.refresh(invitation)
    return invitation, token.raw, outbox


def list_invitations(session: Session, household_id: UUID, limit: int) -> list[HouseholdInvitation]:
    return list(
        session.scalars(
            select(HouseholdInvitation)
            .where(HouseholdInvitation.household_id == household_id)
            .order_by(HouseholdInvitation.created_at.desc())
            .limit(limit)
        )
    )


def revoke_invitation(
    session: Session,
    *,
    invitation_id: UUID,
    household_id: UUID,
    actor: HouseholdMember,
    request_id: str,
) -> None:
    invitation = session.scalar(
        select(HouseholdInvitation).where(
            HouseholdInvitation.id == invitation_id,
            HouseholdInvitation.household_id == household_id,
        )
    )
    if invitation is None:
        raise DomainError(
            "not_found", "Invitation not found", "The invitation could not be found.", 404
        )
    if invitation.status != InvitationStatus.PENDING:
        raise DomainError(
            "conflict", "Invitation conflict", "Only pending invitations can be revoked.", 409
        )
    invitation.status = InvitationStatus.REVOKED
    invitation.revoked_at = datetime.now(UTC)
    invitation.version += 1
    record_audit(
        session,
        actor_user_id=actor.user_id,
        household_id=household_id,
        action="invitation.revoked",
        request_id=request_id,
        target_type="invitation",
        target_id=invitation.id,
    )
    session.commit()


def accept_invitation(
    session: Session,
    *,
    raw_token: str,
    user: AppUser,
    request_id: str,
) -> HouseholdMember:
    if not user.email or not user.email_verified:
        raise DomainError("forbidden", "Permission denied", "A verified email is required.", 403)
    digest = hash_invitation_token(raw_token)
    invitation = session.scalar(
        select(HouseholdInvitation)
        .where(HouseholdInvitation.token_hash == digest)
        .with_for_update()
    )
    if invitation is None:
        raise DomainError(
            "invitation_expired",
            "Invitation unavailable",
            "The invitation is invalid or expired.",
            400,
        )
    now = datetime.now(UTC)
    if not invitation_is_usable(invitation.status, invitation.expires_at, now):
        if invitation.status == InvitationStatus.PENDING:
            invitation.status = InvitationStatus.EXPIRED
            session.commit()
        raise DomainError(
            "invitation_expired",
            "Invitation unavailable",
            "The invitation is invalid or expired.",
            400,
        )
    if normalize_email(user.email) != invitation.invited_email:
        raise DomainError(
            "forbidden",
            "Permission denied",
            "The invitation email does not match the signed-in user.",
            403,
        )
    existing = session.scalar(
        select(HouseholdMember)
        .where(
            HouseholdMember.household_id == invitation.household_id,
            HouseholdMember.user_id == user.id,
        )
        .with_for_update()
    )
    if existing is not None and existing.status == MembershipStatus.ACTIVE:
        raise DomainError(
            "invitation_consumed",
            "Invitation unavailable",
            "The user is already a household member.",
            409,
        )
    if existing is None:
        member = HouseholdMember(
            household_id=invitation.household_id,
            user_id=user.id,
            role=invitation.requested_role,
            status=MembershipStatus.ACTIVE,
        )
        session.add(member)
    else:
        existing.role = invitation.requested_role
        existing.status = MembershipStatus.ACTIVE
        existing.revoked_at = None
        existing.version += 1
        member = existing
    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_by_user_id = user.id
    invitation.accepted_at = now
    invitation.version += 1
    record_audit(
        session,
        actor_user_id=user.id,
        household_id=invitation.household_id,
        action="invitation.accepted",
        request_id=request_id,
        target_type="invitation",
        target_id=invitation.id,
    )
    session.commit()
    session.refresh(member)
    return member
