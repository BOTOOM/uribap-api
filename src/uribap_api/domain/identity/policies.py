import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class MembershipStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    LEFT = "left"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class MembershipAction(StrEnum):
    READ = "read"
    MANAGE_SETTINGS = "manage_settings"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_OWNERSHIP = "manage_ownership"


@dataclass(frozen=True, slots=True)
class InvitationToken:
    raw: str
    digest: str


def normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if len(normalized) > 320 or normalized.count("@") != 1:
        raise ValueError("email must be a valid address")
    local, domain = normalized.split("@")
    if not local or not domain or "." not in domain or any(char.isspace() for char in normalized):
        raise ValueError("email must be a valid address")
    return normalized


def create_invitation_token() -> InvitationToken:
    raw = secrets.token_urlsafe(32)
    return InvitationToken(raw=raw, digest=hashlib.sha256(raw.encode("utf-8")).hexdigest())


def hash_invitation_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_household_name(value: str) -> str:
    normalized = " ".join(value.split())
    if not 1 <= len(normalized) <= 120:
        raise ValueError("household name must contain between 1 and 120 characters")
    if any(ord(char) < 32 for char in normalized):
        raise ValueError("household name must not contain control characters")
    return normalized


def role_allows(role: MembershipRole, action: MembershipAction) -> bool:
    if role == MembershipRole.OWNER:
        return True
    if role == MembershipRole.ADMIN:
        return action in {
            MembershipAction.READ,
            MembershipAction.MANAGE_SETTINGS,
            MembershipAction.MANAGE_MEMBERS,
        }
    return action == MembershipAction.READ


def can_assign_role(actor: MembershipRole, target: MembershipRole) -> bool:
    if actor == MembershipRole.OWNER:
        return target in {MembershipRole.ADMIN, MembershipRole.MEMBER}
    return actor == MembershipRole.ADMIN and target == MembershipRole.MEMBER


def can_remove_membership(actor: MembershipRole, target: MembershipRole) -> bool:
    return actor == MembershipRole.OWNER or (
        actor == MembershipRole.ADMIN and target == MembershipRole.MEMBER
    )


def invitation_is_usable(status: InvitationStatus, expires_at: datetime, now: datetime) -> bool:
    current = now.astimezone(UTC)
    expiry = expires_at.astimezone(UTC)
    return status == InvitationStatus.PENDING and current < expiry
