from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.api.schemas import InvitationCreate
from uribap_api.application.invitation_service import accept_invitation, create_invitation
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.infrastructure.persistence.household_models import (
    Household,
    HouseholdInvitation,
    HouseholdMember,
)
from uribap_api.infrastructure.persistence.identity_models import AppUser


@pytest.mark.integration
def test_invitation_is_hashed_and_consumed_for_verified_email(integration_engine) -> None:
    owner_id = uuid4()
    invitee_id = uuid4()
    household_id = uuid4()
    with Session(integration_engine) as session:
        owner = AppUser(id=owner_id, email=f"owner-{owner_id}@example.test", email_verified=True)
        invitee = AppUser(
            id=invitee_id,
            email=f"invitee-{invitee_id}@example.test",
            email_verified=True,
        )
        session.add_all(
            [
                owner,
                invitee,
                Household(id=household_id, name="Invite Test", locale="es", timezone="UTC"),
            ]
        )
        session.add(
            HouseholdMember(
                household_id=household_id,
                user_id=owner_id,
                role=MembershipRole.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )
        session.commit()
        inviter = session.scalar(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == owner_id,
            )
        )
        assert inviter is not None
        assert invitee.email is not None
        invitation, raw_token, outbox = create_invitation(
            session,
            household_id=household_id,
            inviter=inviter,
            payload=InvitationCreate(email=invitee.email, role="member"),
            request_id="req-invitation-test",
        )
        assert raw_token not in invitation.token_hash
        assert raw_token not in str(outbox.template_data)
        member = accept_invitation(
            session,
            raw_token=raw_token,
            user=invitee,
            request_id="req-accept-test",
        )
        assert member.user_id == invitee_id
        assert member.role == MembershipRole.MEMBER
        stored = session.get(HouseholdInvitation, invitation.id)
        assert stored is not None
        assert stored.status.value == "accepted"
