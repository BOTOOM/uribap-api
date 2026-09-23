from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.mcp_models import McpToken
from uribap_api.mcp import tokens


def _membership(
    session: Session,
    *,
    household_id=None,
    status: MembershipStatus = MembershipStatus.ACTIVE,
) -> tuple[HouseholdMember, AppUser]:
    user_id = uuid4()
    household_id = household_id or uuid4()
    user = AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True)
    session.add(user)
    session.add(Household(id=household_id, name="Isolation", locale="es", timezone="UTC"))
    member = HouseholdMember(
        household_id=household_id,
        user_id=user_id,
        role=MembershipRole.MEMBER,
        status=status,
    )
    session.add(member)
    session.commit()
    return member, user


@pytest.mark.integration
def test_generated_token_hashes_and_prefixes(integration_engine) -> None:
    plaintext, prefix, token_hash = tokens.generate_token()
    assert plaintext.startswith(tokens.TOKEN_PREFIX)
    assert len(plaintext) > 40
    assert prefix == plaintext[:24]
    assert token_hash == tokens.hash_token(plaintext)
    assert plaintext not in token_hash


@pytest.mark.integration
def test_create_token_returns_plaintext_once_and_persists_hash(integration_engine) -> None:
    with Session(integration_engine) as session:
        member, _ = _membership(session)
        token, plaintext = tokens.create_token(session, member, "  Devin Desktop  ")
        assert token.name == "Devin Desktop"
        assert token.token_hash == tokens.hash_token(plaintext)
        assert token.revoked_at is None
        stored = session.get(McpToken, token.id)
        assert stored is not None
        assert plaintext not in (stored.token_prefix, stored.token_hash)


@pytest.mark.integration
def test_resolve_token_returns_principal_scoped_to_household(integration_engine) -> None:
    with Session(integration_engine) as session:
        member, user = _membership(session)
        _, plaintext = tokens.create_token(session, member, "agent")
        principal = tokens.resolve_token(session, plaintext)
        assert principal is not None
        assert principal.user_id == user.id
        assert principal.household_id == member.household_id
        assert principal.role == MembershipRole.MEMBER.value


@pytest.mark.integration
def test_resolve_token_rejects_unknown_garbage_and_revoked(integration_engine) -> None:
    with Session(integration_engine) as session:
        member, _ = _membership(session)
        token, plaintext = tokens.create_token(session, member, "agent")
        assert tokens.resolve_token(session, "uribap_mcp_not-a-real-token") is None
        assert tokens.resolve_token(session, "") is None
        token.revoked_at = datetime.now(UTC)
        session.commit()
        assert tokens.resolve_token(session, plaintext) is None


@pytest.mark.integration
def test_resolve_token_rejects_inactive_membership(integration_engine) -> None:
    with Session(integration_engine) as session:
        member, _ = _membership(session)
        _, plaintext = tokens.create_token(session, member, "agent")
        member.status = MembershipStatus.REVOKED
        session.commit()
        assert tokens.resolve_token(session, plaintext) is None


@pytest.mark.integration
def test_list_and_revoke_are_scoped_to_user_and_household(integration_engine) -> None:
    with Session(integration_engine) as session:
        member_a, _ = _membership(session)
        member_b, _ = _membership(session)
        other_household_member, _ = _membership(session)
        token_a1, _ = tokens.create_token(session, member_a, "a1")
        tokens.create_token(session, member_a, "a2")
        token_b, _ = tokens.create_token(session, member_b, "b-same-household")
        tokens.create_token(session, other_household_member, "other")

        assert {t.name for t in tokens.list_tokens(session, member_a)} == {"a1", "a2"}

        # member_b belongs to a different household: cannot see or revoke a's tokens.
        assert {t.name for t in tokens.list_tokens(session, member_b)} == {"b-same-household"}
        assert tokens.revoke_token(session, member_b, token_a1.id) is False
        assert tokens.revoke_token(session, member_a, token_a1.id) is True
        assert tokens.revoke_token(session, member_a, token_a1.id) is False
        assert {t.name for t in tokens.list_tokens(session, member_a)} == {"a2"}
        assert token_b.name == "b-same-household"


@pytest.mark.integration
def test_last_used_at_updates_on_resolve(integration_engine) -> None:
    with Session(integration_engine) as session:
        member, _ = _membership(session)
        token, plaintext = tokens.create_token(session, member, "agent")
        assert token.last_used_at is None
        tokens.resolve_token(session, plaintext)
        session.refresh(token)
        assert token.last_used_at is not None
