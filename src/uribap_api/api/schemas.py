from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, Field, field_validator

UnitCode = Literal["unit", "g", "kg", "ml", "l"]


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
