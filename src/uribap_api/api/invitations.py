import logging
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import (
    get_current_user,
    get_session,
    request_id,
    require_household_membership,
)
from uribap_api.api.schemas import (
    InvitationAccept,
    InvitationCreate,
    InvitationPage,
    InvitationResponse,
    InvitationRole,
    MemberResponse,
    PageInfo,
)
from uribap_api.application.invitation_service import (
    accept_invitation,
    create_invitation,
    list_invitations,
    revoke_invitation,
)
from uribap_api.domain.identity.policies import MembershipRole
from uribap_api.infrastructure.email.mailer import send_outbox_entry
from uribap_api.infrastructure.email.outbox import mark_failed, mark_sent
from uribap_api.infrastructure.persistence.household_models import (
    HouseholdInvitation,
    HouseholdMember,
)
from uribap_api.infrastructure.persistence.identity_models import AppUser

logger = logging.getLogger(__name__)
router = APIRouter(tags=["invitations"])


def invitation_response(invitation: HouseholdInvitation) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        household_id=invitation.household_id,
        email=invitation.invited_email,
        requested_role=cast(InvitationRole, invitation.requested_role.value),
        status=invitation.status.value,
        expires_at=invitation.expires_at,
        invited_by_user_id=invitation.invited_by_user_id,
        created_at=invitation.created_at,
    )


@router.get("/households/{household_id}/invitations", response_model=InvitationPage)
def list_household_invitations(
    household_id: UUID,
    limit: int = 50,
    _: HouseholdMember = Depends(
        require_household_membership(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    session: Session = Depends(get_session),
) -> InvitationPage:
    invitations = list_invitations(session, household_id, min(limit, 100))
    return InvitationPage(
        items=[invitation_response(invitation) for invitation in invitations],
        page_info=PageInfo(limit=min(limit, 100)),
    )


@router.post(
    "/households/{household_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_household_invitation(
    household_id: UUID,
    payload: InvitationCreate,
    request: Request,
    inviter: HouseholdMember = Depends(
        require_household_membership(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    session: Session = Depends(get_session),
    correlation_id: str = Depends(request_id),
) -> InvitationResponse:
    invitation, raw_token, outbox = create_invitation(
        session,
        household_id=household_id,
        inviter=inviter,
        payload=payload,
        request_id=correlation_id,
    )
    settings = request.app.state.settings
    try:
        send_outbox_entry(
            settings,
            outbox,
            link=f"{settings.web_base_url.rstrip('/')}/invitations/accept?token={raw_token}",
        )
    except Exception:
        logger.exception("identity email delivery failed", extra={"request_id": correlation_id})
        mark_failed(session, outbox.id, "smtp delivery failed")
        session.commit()
    else:
        mark_sent(session, outbox.id)
        session.commit()
    return invitation_response(invitation)


@router.delete(
    "/households/{household_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_household_invitation(
    household_id: UUID,
    invitation_id: UUID,
    response: Response,
    actor: HouseholdMember = Depends(
        require_household_membership(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    session: Session = Depends(get_session),
    correlation_id: str = Depends(request_id),
) -> None:
    revoke_invitation(
        session,
        invitation_id=invitation_id,
        household_id=household_id,
        actor=actor,
        request_id=correlation_id,
    )
    response.status_code = status.HTTP_204_NO_CONTENT


@router.post("/invitations/accept", response_model=MemberResponse)
def accept_household_invitation(
    payload: InvitationAccept,
    user: AppUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    correlation_id: str = Depends(request_id),
) -> MemberResponse:
    membership = accept_invitation(
        session,
        raw_token=payload.token,
        user=user,
        request_id=correlation_id,
    )
    return MemberResponse(
        id=membership.id,
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
        email_verified=user.email_verified,
        role=membership.role.value,
        status=membership.status.value,
        version=membership.version,
        joined_at=membership.joined_at,
    )
