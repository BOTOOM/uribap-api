from uuid import uuid4

import pytest
from pydantic import ValidationError

from uribap_api.api.memory_schemas import DinerCreate, DinerUpdate, MemoryCreate, MemoryUpdate
from uribap_api.domain.household.memory import MemoryKind


def test_memory_kind_values_are_stable() -> None:
    assert [kind.value for kind in MemoryKind] == [
        "like",
        "dislike",
        "restriction",
        "goal",
        "note",
    ]


def test_diner_create_trims_name_and_accepts_optional_member_link() -> None:
    member_user_id = uuid4()
    diner = DinerCreate(display_name="  Alex  ", member_user_id=member_user_id)

    assert diner.display_name == "Alex"
    assert diner.member_user_id == member_user_id


@pytest.mark.parametrize("display_name", ["", " ", "x" * 81])
def test_diner_create_rejects_invalid_trimmed_name(display_name: str) -> None:
    with pytest.raises(ValidationError):
        DinerCreate(display_name=display_name)


def test_diner_update_requires_version_and_a_change() -> None:
    with pytest.raises(ValidationError):
        DinerUpdate.model_validate({"display_name": "Alex"})
    with pytest.raises(ValidationError):
        DinerUpdate(expected_version=1)
    with pytest.raises(ValidationError):
        DinerUpdate(expected_version=0, display_name="Alex")


def test_diner_update_preserves_explicit_null_member_link() -> None:
    update = DinerUpdate(expected_version=1, member_user_id=None)

    assert "member_user_id" in update.model_fields_set
    assert update.member_user_id is None


def test_memory_create_trims_content_and_defaults_no_kind_only_at_mcp_boundary() -> None:
    memory = MemoryCreate(kind=MemoryKind.LIKE, content="  Likes lentils  ")

    assert memory.kind is MemoryKind.LIKE
    assert memory.content == "Likes lentils"
    with pytest.raises(ValidationError):
        MemoryCreate.model_validate({"content": "No kind"})


@pytest.mark.parametrize("content", ["", " ", "x" * 1001])
def test_memory_create_rejects_invalid_trimmed_content(content: str) -> None:
    with pytest.raises(ValidationError):
        MemoryCreate(kind=MemoryKind.NOTE, content=content)


def test_memory_update_requires_version_and_a_change() -> None:
    with pytest.raises(ValidationError):
        MemoryUpdate.model_validate({"content": "New content"})
    with pytest.raises(ValidationError):
        MemoryUpdate(expected_version=1)


def test_memory_update_preserves_explicit_null_diner_scope() -> None:
    update = MemoryUpdate(expected_version=1, diner_id=None)

    assert "diner_id" in update.model_fields_set
    assert update.diner_id is None
