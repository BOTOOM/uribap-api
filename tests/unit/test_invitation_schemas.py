import pytest
from pydantic import ValidationError

from uribap_api.api.schemas import InvitationCreate


def test_invitation_create_trims_or_omits_display_name() -> None:
    assert (
        InvitationCreate(
            email="person@example.test",
            display_name="  Ada Lovelace  ",
        ).display_name
        == "Ada Lovelace"
    )
    assert (
        InvitationCreate(
            email="person@example.test",
            display_name="   ",
        ).display_name
        is None
    )


def test_invitation_create_rejects_display_names_over_200_characters() -> None:
    with pytest.raises(ValidationError):
        InvitationCreate(email="person@example.test", display_name="a" * 201)
