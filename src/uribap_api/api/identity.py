from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_current_user, get_session
from uribap_api.api.schemas import CurrentUserResponse, MembershipResponse
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser

router = APIRouter(tags=["identity"])


@router.get("/me", response_model=CurrentUserResponse)
def current_user(
    user: AppUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CurrentUserResponse:
    rows = session.execute(
        select(HouseholdMember, Household)
        .join(Household, Household.id == HouseholdMember.household_id)
        .where(HouseholdMember.user_id == user.id, HouseholdMember.status == "active")
        .order_by(HouseholdMember.joined_at)
    )
    memberships = [
        MembershipResponse(
            id=membership.id,
            household_id=membership.household_id,
            household_name=household.name,
            role=membership.role.value,
            status=membership.status.value,
            version=membership.version,
            joined_at=membership.joined_at,
        )
        for membership, household in rows.all()
    ]
    return CurrentUserResponse(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        email_verified=user.email_verified,
        memberships=memberships,
    )
