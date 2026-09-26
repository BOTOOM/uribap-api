from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from uribap_api.application.identity_service import provision_user
from uribap_api.domain.identity.policies import UserStatus
from uribap_api.infrastructure.identity.claims import IdentityClaims
from uribap_api.infrastructure.persistence.identity_models import AppUser


def claims(*, email: str | None, email_verified: bool) -> IdentityClaims:
    return IdentityClaims(
        issuer="https://issuer.example.test",
        subject="synthetic-subject",
        email=email,
        email_verified=email_verified,
        display_name=None,
        scopes=frozenset(),
        raw={},
    )


def existing_user_session() -> tuple[Mock, AppUser]:
    user = AppUser(
        id=uuid4(),
        email="old@example.test",
        email_verified=True,
        status=UserStatus.ACTIVE,
    )
    session = Mock(spec=Session)
    session.scalar.return_value = SimpleNamespace(user=user)
    return session, user


@pytest.mark.parametrize(
    ("email", "expected_email"),
    [(None, "old@example.test"), ("not-an-email", "old@example.test")],
)
def test_existing_user_email_retention_does_not_retain_verification(
    email: str | None, expected_email: str
) -> None:
    session, user = existing_user_session()

    provisioned = provision_user(session, claims(email=email, email_verified=True))

    assert provisioned is user
    assert user.email == expected_email
    assert user.email_verified is False


def test_existing_user_replaces_email_but_keeps_it_unverified() -> None:
    session, user = existing_user_session()

    provisioned = provision_user(
        session,
        claims(email="  NEW@Example.Test  ", email_verified=False),
    )

    assert provisioned is user
    assert user.email == "new@example.test"
    assert user.email_verified is False


def test_existing_user_receives_normalized_verified_email() -> None:
    session, user = existing_user_session()

    provisioned = provision_user(
        session,
        claims(email="  PERSON@Example.Test  ", email_verified=True),
    )

    assert provisioned is user
    assert user.email == "person@example.test"
    assert user.email_verified is True


@pytest.mark.parametrize("email", [None, "not-an-email"])
def test_new_user_without_valid_email_is_never_verified(email: str | None) -> None:
    session = Mock(spec=Session)
    session.scalar.return_value = None

    provisioned = provision_user(session, claims(email=email, email_verified=True))

    assert provisioned.email is None
    assert provisioned.email_verified is False
    session.add.assert_any_call(provisioned)
