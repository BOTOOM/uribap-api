from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from uribap_api.domain.inventory.ledger import (
    InventoryLocation,
    InventoryMovementType,
    validate_delta,
    validate_quantity,
)


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
        return validate_quantity(value)


class InventoryAdjustment(BaseModel):
    lot_id: UUID
    delta: Decimal
    unit: str
    movement_type: InventoryMovementType = InventoryMovementType.MANUAL_ADJUSTMENT
    source_type: str | None = None
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
    idempotency_key: str | None
    created_at: datetime


class InventoryPage(BaseModel):
    items: list[InventoryLotResponse]


class InventoryMovementPage(BaseModel):
    items: list[InventoryMovementResponse]
