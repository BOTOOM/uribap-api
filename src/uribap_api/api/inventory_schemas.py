from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from uribap_api.domain.inventory.ledger import (
    InventoryLocation,
    InventoryMovementType,
    quantize_amount,
    validate_delta,
)


class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    code: str
    requestId: str | None = None


class InventoryLotCreate(BaseModel):
    ingredient_id: UUID
    quantity: Decimal = Field(gt=0)
    unit: str
    location: InventoryLocation
    expiration_date: date | None = None
    notes: str | None = None

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, value: Decimal) -> Decimal:
        return quantize_amount(value, allow_zero=False)


class InventoryAdjustment(BaseModel):
    lot_id: UUID
    delta: Decimal
    unit: str
    movement_type: InventoryMovementType = InventoryMovementType.MANUAL_ADJUSTMENT
    source_type: str | None = Field(default=None, max_length=80)
    source_id: UUID | None = None

    @field_validator("delta")
    @classmethod
    def nonzero_delta(cls, value: Decimal) -> Decimal:
        return validate_delta(value)


class InventoryLotResponse(BaseModel):
    id: UUID
    household_id: UUID
    ingredient_id: UUID
    quantity_on_hand: Decimal
    unit: str
    location: InventoryLocation
    available: bool
    expired: bool
    expiration_date: date | None
    notes: str | None
    updated_at: datetime


class InventoryMovementResponse(BaseModel):
    id: UUID
    lot_id: UUID
    delta: Decimal
    unit: str
    movement_type: InventoryMovementType
    actor_user_id: UUID
    source_type: str | None
    source_id: UUID | None
    operation: str
    idempotency_key: str | None
    request_hash: str | None
    result_quantity_on_hand: Decimal | None
    created_at: datetime


class InventoryPage(BaseModel):
    items: list[InventoryLotResponse]


class InventoryMovementPage(BaseModel):
    items: list[InventoryMovementResponse]
