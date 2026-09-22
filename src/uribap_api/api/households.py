from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import (
    get_current_user,
    get_session,
    request_id,
    require_household_membership,
)
from uribap_api.api.event_schemas import (
    ActivityEntry,
    ActivityFeedResponse,
    OutboxSummary,
)
from uribap_api.api.inventory_schemas import ProblemDetails
from uribap_api.api.schemas import (
    HouseholdCreate,
    HouseholdResponse,
    HouseholdUpdate,
    HouseholdWithMembership,
    MemberPage,
    MemberResponse,
    MemberRoleUpdate,
    MembershipResponse,
    PageInfo,
)
from uribap_api.application.event_service import list_activity
from uribap_api.application.household_service import (
    create_household,
    get_household,
    list_members,
    revoke_member,
    update_household,
    update_member_role,
)
from uribap_api.domain.identity.policies import MembershipRole
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser

router = APIRouter(prefix="/households", tags=["households"])

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


def household_response(household: Household) -> HouseholdResponse:
    return HouseholdResponse(
        id=household.id,
        name=household.name,
        locale=household.locale,
        timezone=household.timezone,
        status=household.status.value,
        version=household.version,
        created_at=household.created_at,
        updated_at=household.updated_at,
    )


def member_response(member: HouseholdMember, user: AppUser) -> MemberResponse:
    return MemberResponse(
        id=member.id,
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
        email_verified=user.email_verified,
        role=member.role.value,
        status=member.status.value,
        version=member.version,
        joined_at=member.joined_at,
    )


@router.post("", response_model=HouseholdWithMembership, status_code=status.HTTP_201_CREATED)
def create(
    payload: HouseholdCreate,
    user: AppUser = Depends(get_current_user),
    session: Session = Depends(get_session),
    correlation_id: str = Depends(request_id),
) -> HouseholdWithMembership:
    household, membership = create_household(
        session, user=user, payload=payload, request_id=correlation_id
    )
    return HouseholdWithMembership(
        household=household_response(household),
        membership=MembershipResponse(
            id=membership.id,
            household_id=membership.household_id,
            household_name=household.name,
            role=membership.role.value,
            status=membership.status.value,
            version=membership.version,
            joined_at=membership.joined_at,
        ),
    )


@router.get("/{household_id}", response_model=HouseholdResponse)
def read(
    household_id: UUID,
    _: HouseholdMember = Depends(require_household_membership()),
    session: Session = Depends(get_session),
) -> HouseholdResponse:
    return household_response(get_household(session, household_id))


@router.patch("/{household_id}", response_model=HouseholdResponse)
def update(
    household_id: UUID,
    payload: HouseholdUpdate,
    if_match: int | None = Header(default=None, alias="If-Match"),
    membership: HouseholdMember = Depends(
        require_household_membership(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    session: Session = Depends(get_session),
    correlation_id: str = Depends(request_id),
) -> HouseholdResponse:
    household = get_household(session, household_id)
    user = session.get(AppUser, membership.user_id)
    if user is None:
        raise RuntimeError("membership user missing")
    return household_response(
        update_household(
            session,
            household=household,
            user=user,
            payload=payload,
            expected_version=if_match,
            request_id=correlation_id,
        )
    )


@router.get(
    "/{household_id}/activity",
    response_model=ActivityFeedResponse,
    responses=ERROR_RESPONSES,
)
def activity(
    household_id: UUID,
    page: int = 1,
    page_size: int = 20,
    membership: HouseholdMember = Depends(require_household_membership()),
    session: Session = Depends(get_session),
) -> ActivityFeedResponse:
    entries, has_more, summary = list_activity(
        session,
        membership,
        page=max(page, 1),
        page_size=min(max(page_size, 1), 100),
    )
    return ActivityFeedResponse(
        entries=[
            ActivityEntry(
                id=event.id,
                kind=event.kind,
                occurred_at=event.occurred_at,
                actor_user_id=event.actor_user_id,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                payload=event.payload,
            )
            for event in entries
        ],
        page=max(page, 1),
        page_size=min(max(page_size, 1), 100),
        has_more=has_more,
        outbox=OutboxSummary(**summary),
    )


@router.get("/{household_id}/members", response_model=MemberPage)
def members(
    household_id: UUID,
    limit: int = 50,
    _: HouseholdMember = Depends(require_household_membership()),
    session: Session = Depends(get_session),
) -> MemberPage:
    rows = list_members(session, household_id, min(limit, 100))
    return MemberPage(
        items=[member_response(member, user) for member, user in rows],
        page_info=PageInfo(limit=min(limit, 100)),
    )


@router.patch("/{household_id}/members/{user_id}", response_model=MemberResponse)
def update_member(
    household_id: UUID,
    user_id: UUID,
    payload: MemberRoleUpdate,
    if_match: int | None = Header(default=None, alias="If-Match"),
    actor: HouseholdMember = Depends(
        require_household_membership(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    session: Session = Depends(get_session),
    correlation_id: str = Depends(request_id),
) -> MemberResponse:
    member = update_member_role(
        session,
        household_id=household_id,
        actor=actor,
        target_user_id=user_id,
        payload=payload,
        expected_version=if_match,
        request_id=correlation_id,
    )
    user = session.get(AppUser, user_id)
    if user is None:
        raise RuntimeError("membership user missing")
    return member_response(member, user)


@router.delete("/{household_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(
    household_id: UUID,
    user_id: UUID,
    response: Response,
    if_match: int | None = Header(default=None, alias="If-Match"),
    actor: HouseholdMember = Depends(
        require_household_membership(MembershipRole.OWNER, MembershipRole.ADMIN)
    ),
    session: Session = Depends(get_session),
    correlation_id: str = Depends(request_id),
) -> None:
    revoke_member(
        session,
        household_id=household_id,
        actor=actor,
        target_user_id=user_id,
        expected_version=if_match,
        request_id=correlation_id,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
