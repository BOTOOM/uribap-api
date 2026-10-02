from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from uribap_api.domain.household.memory import MemoryKind


class DinerCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    member_user_id: UUID | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class DinerUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    member_user_id: UUID | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def trim_display_name(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_changes(self) -> DinerUpdate:
        changes = self.model_fields_set - {"expected_version"}
        if not changes:
            raise ValueError("At least one diner field must be provided.")
        if "display_name" in changes and self.display_name is None:
            raise ValueError("display_name cannot be null.")
        return self


class MemoryCreate(BaseModel):
    kind: MemoryKind
    content: str = Field(min_length=1, max_length=1000)
    diner_id: UUID | None = None

    @field_validator("content", mode="before")
    @classmethod
    def trim_content(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class MemoryUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    kind: MemoryKind | None = None
    content: str | None = Field(default=None, min_length=1, max_length=1000)
    diner_id: UUID | None = None

    @field_validator("content", mode="before")
    @classmethod
    def trim_content(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_changes(self) -> MemoryUpdate:
        changes = self.model_fields_set - {"expected_version"}
        if not changes:
            raise ValueError("At least one memory field must be provided.")
        if "content" in changes and self.content is None:
            raise ValueError("content cannot be null.")
        if "kind" in changes and self.kind is None:
            raise ValueError("kind cannot be null.")
        return self


class DinerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    member_user_id: UUID | None
    archived_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class MemoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    diner_id: UUID | None
    kind: MemoryKind
    content: str
    archived_at: datetime | None
    version: int
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class DinerPage(BaseModel):
    items: list[DinerResponse]


class MemoryPage(BaseModel):
    items: list[MemoryResponse]


class DinerMemoryProfile(BaseModel):
    diner: DinerResponse
    memories: list[MemoryResponse]


class HouseholdMemoryProfile(BaseModel):
    household: list[MemoryResponse]
    diners: list[DinerMemoryProfile]
