from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.domain.identity.policies import MembershipStatus, UserStatus
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.mcp_models import McpToken

TOKEN_PREFIX = "uribap_mcp_"
_LAST_USED_GRACE = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class McpPrincipal:
    """Detached identity resolved from an MCP bearer token.

    Holds plain values only: ORM objects would expire once the middleware
    session commits/closes, so tools reload the membership per call.
    """

    user_id: UUID
    household_id: UUID
    role: str
    display_name: str | None
    email: str | None


def generate_token() -> tuple[str, str, str]:
    """Return (plaintext, display_prefix, sha256_hash) for a new agent token."""
    plaintext = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    return plaintext, plaintext[:24], hash_token(plaintext)


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def create_token(
    session: Session, membership: HouseholdMember, name: str
) -> tuple[McpToken, str]:
    plaintext, prefix, token_hash = generate_token()
    token = McpToken(
        household_id=membership.household_id,
        user_id=membership.user_id,
        name=name.strip() or "MCP token",
        token_prefix=prefix,
        token_hash=token_hash,
    )
    session.add(token)
    session.commit()
    session.refresh(token)
    return token, plaintext


def list_tokens(session: Session, membership: HouseholdMember) -> list[McpToken]:
    return list(
        session.scalars(
            select(McpToken)
            .where(
                McpToken.user_id == membership.user_id,
                McpToken.household_id == membership.household_id,
                McpToken.revoked_at.is_(None),
            )
            .order_by(McpToken.created_at.desc(), McpToken.id)
        )
    )


def revoke_token(session: Session, membership: HouseholdMember, token_id: UUID) -> bool:
    token = session.scalar(
        select(McpToken).where(
            McpToken.id == token_id,
            McpToken.user_id == membership.user_id,
            McpToken.household_id == membership.household_id,
            McpToken.revoked_at.is_(None),
        )
    )
    if token is None:
        return False
    token.revoked_at = datetime.now(UTC)
    session.commit()
    return True


def resolve_token(session: Session, plaintext: str) -> McpPrincipal | None:
    """Resolve a bearer token into an active user + household membership."""
    token = session.scalar(
        select(McpToken).where(
            McpToken.token_hash == hash_token(plaintext), McpToken.revoked_at.is_(None)
        )
    )
    if token is None:
        return None
    user = session.get(AppUser, token.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        return None
    membership = session.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == token.household_id,
            HouseholdMember.user_id == token.user_id,
            HouseholdMember.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        return None
    principal = McpPrincipal(
        user_id=user.id,
        household_id=membership.household_id,
        role=membership.role.value,
        display_name=user.display_name,
        email=user.email,
    )
    now = datetime.now(UTC)
    last = token.last_used_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    if last is None or now - last > _LAST_USED_GRACE:
        token.last_used_at = now
        session.commit()
    return principal


def load_membership(session: Session, principal: McpPrincipal) -> HouseholdMember:
    """Reload the caller's active membership inside a tool's own session."""
    membership = session.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == principal.household_id,
            HouseholdMember.user_id == principal.user_id,
            HouseholdMember.status == MembershipStatus.ACTIVE,
        )
    )
    if membership is None:
        from uribap_api.domain.shared.errors import DomainError

        raise DomainError(
            "forbidden", "Permission denied", "The token's membership is no longer active.", 403
        )
    return membership
