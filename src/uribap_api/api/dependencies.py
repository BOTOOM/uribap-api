from collections.abc import Generator
from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.application.identity_service import provision_user
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.database import get_db_session
from uribap_api.infrastructure.identity.claims import IdentityClaims
from uribap_api.infrastructure.logging import get_request_id
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    claims: IdentityClaims
    user: AppUser


def get_session(request: Request) -> Generator[Session]:
    session_factory = request.app.state.session_factory
    yield from get_db_session(session_factory)


async def get_identity_claims(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> IdentityClaims:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise DomainError(
            "unauthorized", "Authentication required", "A bearer token is required.", 401
        )
    return await request.app.state.token_validator.validate(credentials.credentials)


def get_current_principal(
    claims: IdentityClaims = Depends(get_identity_claims),
    session: Session = Depends(get_session),
) -> AuthenticatedPrincipal:
    user = provision_user(session, claims)
    if user.status.value != "active":
        raise DomainError("forbidden", "Permission denied", "The user is disabled.", 403)
    return AuthenticatedPrincipal(claims=claims, user=user)


def get_current_user(
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> AppUser:
    return principal.user


def require_household_membership(*roles: MembershipRole):
    allowed = set(roles)

    def dependency(
        household_id: UUID,
        user: AppUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ) -> HouseholdMember:
        membership = session.scalar(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == user.id,
                HouseholdMember.status == MembershipStatus.ACTIVE,
            )
        )
        if membership is None:
            raise DomainError(
                "forbidden", "Permission denied", "The user is not a household member.", 403
            )
        if allowed and membership.role not in allowed:
            raise DomainError(
                "forbidden", "Permission denied", "The user lacks this household role.", 403
            )
        return membership

    return dependency


def request_id() -> str:
    return get_request_id()
