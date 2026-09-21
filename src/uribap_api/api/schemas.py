from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from uribap_api.domain.identity.policies import normalize_email, validate_household_name

UnitCode = Literal["unit", "g", "kg", "ml", "l"]
Role = Literal["owner", "admin", "member"]
InvitationRole = Literal["admin", "member"]


class Quantity(BaseModel):
    amount: str = Field(pattern=r"^\d+(\.\d+)?$", min_length=1)
    unit: UnitCode

    @field_validator("amount")
    @classmethod
    def validate_decimal_amount(cls, value: str) -> str:
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("amount must be a decimal value") from exc
        if amount < 0:
            raise ValueError("amount must not be negative")
        return format(amount, "f")


class PageInfo(BaseModel):
    next_cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=100)


class MutationMeta(BaseModel):
    projection_revision: int | None = Field(default=None, ge=0)
    idempotency_key: str | None = None
    expected_version: int | None = Field(default=None, ge=0)


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    household_id: UUID
    household_name: str
    role: Role
    status: str
    version: int
    joined_at: datetime


class CurrentUserResponse(BaseModel):
    id: UUID
    display_name: str | None
    email: str | None
    email_verified: bool
    memberships: list[MembershipResponse]


class HouseholdCreate(BaseModel):
    name: str
    locale: str = Field(default="es", min_length=2, max_length=32)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validate_household_name(value)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class HouseholdUpdate(BaseModel):
    name: str | None = None
    locale: str | None = Field(default=None, min_length=2, max_length=32)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return validate_household_name(value) if value is not None else None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class HouseholdResponse(BaseModel):
    id: UUID
    name: str
    locale: str
    timezone: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class HouseholdWithMembership(BaseModel):
    household: HouseholdResponse
    membership: MembershipResponse


class MemberResponse(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str | None
    email: str | None
    email_verified: bool
    role: Role
    status: str
    version: int
    joined_at: datetime


class MemberPage(BaseModel):
    items: list[MemberResponse]
    page_info: PageInfo


class MemberRoleUpdate(BaseModel):
    role: Literal["admin", "member"]


class InvitationCreate(BaseModel):
    email: str
    role: InvitationRole = "member"
    expires_in_hours: int = Field(default=72, ge=1, le=168)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class InvitationResponse(BaseModel):
    id: UUID
    household_id: UUID
    email: str
    requested_role: InvitationRole
    status: str
    expires_at: datetime
    invited_by_user_id: UUID
    created_at: datetime


class InvitationPage(BaseModel):
    items: list[InvitationResponse]
    page_info: PageInfo


class InvitationAccept(BaseModel):
    token: str = Field(min_length=20, max_length=512)
