from datetime import UTC, datetime, timedelta

import pytest

from uribap_api.domain.identity.policies import (
    InvitationStatus,
    MembershipAction,
    MembershipRole,
    can_assign_role,
    create_invitation_token,
    hash_invitation_token,
    invitation_is_usable,
    normalize_email,
    role_allows,
    validate_household_name,
)


def test_normalize_email_and_household_name() -> None:
    assert normalize_email(" Person@Example.TEST ") == "person@example.test"
    assert validate_household_name("  Casa   Dos  ") == "Casa Dos"


def test_invalid_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_email("invalid")
    with pytest.raises(ValueError):
        validate_household_name("\n")


def test_invitation_token_is_hashed_and_usable_once_by_policy() -> None:
    token = create_invitation_token()
    assert token.raw
    assert token.digest == hash_invitation_token(token.raw)
    assert token.raw != token.digest
    now = datetime.now(UTC)
    assert invitation_is_usable(InvitationStatus.PENDING, now + timedelta(hours=1), now)
    assert not invitation_is_usable(InvitationStatus.ACCEPTED, now + timedelta(hours=1), now)
    assert not invitation_is_usable(InvitationStatus.PENDING, now - timedelta(seconds=1), now)


def test_roles_are_explicitly_scoped() -> None:
    assert role_allows(MembershipRole.OWNER, MembershipAction.MANAGE_OWNERSHIP)
    assert role_allows(MembershipRole.ADMIN, MembershipAction.MANAGE_MEMBERS)
    assert not role_allows(MembershipRole.MEMBER, MembershipAction.MANAGE_SETTINGS)
    assert can_assign_role(MembershipRole.OWNER, MembershipRole.ADMIN)
    assert can_assign_role(MembershipRole.ADMIN, MembershipRole.MEMBER)
    assert not can_assign_role(MembershipRole.ADMIN, MembershipRole.ADMIN)
