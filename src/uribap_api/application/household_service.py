from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from uribap_api.api.schemas import HouseholdCreate, HouseholdUpdate, MemberRoleUpdate
from uribap_api.application.audit_service import record_audit
from uribap_api.application.event_service import record_event
from uribap_api.domain.events.policies import DomainEventKind
from uribap_api.domain.identity.policies import (
    MembershipRole,
    MembershipStatus,
    can_assign_role,
    can_remove_membership,
)
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import (
    Household,
    HouseholdMember,
    HouseholdStatus,
)
from uribap_api.infrastructure.persistence.identity_models import AppUser


def create_household(
    session: Session,
    *,
    user: AppUser,
    payload: HouseholdCreate,
    request_id: str,
) -> tuple[Household, HouseholdMember]:
    household = Household(name=payload.name, locale=payload.locale, timezone=payload.timezone)
    session.add(household)
    session.flush()
    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(membership)
    record_audit(
        session,
        actor_user_id=user.id,
        household_id=household.id,
        action="household.created",
        request_id=request_id,
        target_type="household",
        target_id=household.id,
    )
    record_event(
        session,
        household_id=household.id,
        kind=DomainEventKind.MEMBER_ADDED,
        actor_user_id=user.id,
        aggregate_type="household_member",
        aggregate_id=membership.id,
        payload={"role": membership.role.value},
    )
    session.commit()
    session.refresh(household)
    session.refresh(membership)
    return household, membership


def get_household(session: Session, household_id: UUID) -> Household:
    household = session.get(Household, household_id)
    if household is None or household.status != HouseholdStatus.ACTIVE:
        raise DomainError(
            "not_found", "Household not found", "The household could not be found.", 404
        )
    return household


def update_household(
    session: Session,
    *,
    household: Household,
    user: AppUser,
    payload: HouseholdUpdate,
    expected_version: int | None,
    request_id: str,
) -> Household:
    if expected_version is not None and household.version != expected_version:
        raise DomainError("conflict", "Conflict", "The household version is stale.", 409)
    if payload.name is not None:
        household.name = payload.name
    if payload.locale is not None:
        household.locale = payload.locale
    if payload.timezone is not None:
        household.timezone = payload.timezone
    household.version += 1
    record_audit(
        session,
        actor_user_id=user.id,
        household_id=household.id,
        action="household.updated",
        request_id=request_id,
        target_type="household",
        target_id=household.id,
    )
    session.commit()
    session.refresh(household)
    return household


def list_members(
    session: Session, household_id: UUID, limit: int
) -> list[tuple[HouseholdMember, AppUser]]:
    rows = session.execute(
        select(HouseholdMember, AppUser)
        .join(AppUser, AppUser.id == HouseholdMember.user_id)
        .where(HouseholdMember.household_id == household_id)
        .order_by(HouseholdMember.joined_at, HouseholdMember.id)
        .limit(limit)
    )
    return list(rows.tuples().all())


def update_member_role(
    session: Session,
    *,
    household_id: UUID,
    actor: HouseholdMember,
    target_user_id: UUID,
    payload: MemberRoleUpdate,
    expected_version: int | None,
    request_id: str,
) -> HouseholdMember:
    target = session.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == target_user_id,
        )
    )
    if target is None or target.status != MembershipStatus.ACTIVE:
        raise DomainError(
            "not_found", "Member not found", "The household member could not be found.", 404
        )
    requested_role = MembershipRole(payload.role)
    if not can_assign_role(actor.role, requested_role) or target.role == MembershipRole.OWNER:
        raise DomainError(
            "forbidden", "Permission denied", "The member role cannot be changed.", 403
        )
    if expected_version is not None and target.version != expected_version:
        raise DomainError("conflict", "Conflict", "The member version is stale.", 409)
    target.role = requested_role
    target.version += 1
    record_audit(
        session,
        actor_user_id=actor.user_id,
        household_id=household_id,
        action="membership.role_changed",
        request_id=request_id,
        target_type="user",
        target_id=target.user_id,
        metadata={"role": requested_role.value},
    )
    session.commit()
    session.refresh(target)
    return target


def revoke_member(
    session: Session,
    *,
    household_id: UUID,
    actor: HouseholdMember,
    target_user_id: UUID,
    expected_version: int | None,
    request_id: str,
) -> None:
    target = session.scalar(
        select(HouseholdMember)
        .where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == target_user_id,
        )
        .with_for_update()
    )
    if target is None or target.status != MembershipStatus.ACTIVE:
        raise DomainError(
            "not_found", "Member not found", "The household member could not be found.", 404
        )
    if not can_remove_membership(actor.role, target.role):
        raise DomainError("forbidden", "Permission denied", "The member cannot be revoked.", 403)
    if expected_version is not None and target.version != expected_version:
        raise DomainError("conflict", "Conflict", "The member version is stale.", 409)
    if target.role == MembershipRole.OWNER:
        owner_count = session.scalar(
            select(func.count())
            .select_from(HouseholdMember)
            .where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.role == MembershipRole.OWNER,
                HouseholdMember.status == MembershipStatus.ACTIVE,
            )
        )
        if owner_count == 1:
            raise DomainError(
                "conflict", "Owner required", "A household must retain an active owner.", 409
            )
    target.status = MembershipStatus.REVOKED
    target.revoked_at = datetime.now(UTC)
    target.version += 1
    record_audit(
        session,
        actor_user_id=actor.user_id,
        household_id=household_id,
        action="membership.revoked",
        request_id=request_id,
        target_type="user",
        target_id=target.user_id,
    )
    record_event(
        session,
        household_id=household_id,
        kind=DomainEventKind.MEMBER_REMOVED,
        actor_user_id=actor.user_id,
        aggregate_type="household_member",
        aggregate_id=target.id,
        payload={"role": target.role.value},
    )
    session.commit()
