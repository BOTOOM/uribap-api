from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from uribap_api.domain.forecast.policies import DemandForecastError, validate_window
from uribap_api.domain.inventory.ledger import InventoryLocation
from uribap_api.domain.shopping.policies import (
    ShoppingItemStatus,
    ShoppingListState,
    validate_purchase_amount,
)


class ShoppingListCreate(BaseModel):
    from_date: date
    to_date: date

    @field_validator("to_date")
    @classmethod
    def valid_window(cls, value: date, info) -> date:
        from_date = info.data.get("from_date")
        if from_date is None:
            return value
        try:
            validate_window(from_date, value)
        except DemandForecastError as exc:
            raise ValueError(str(exc)) from exc
        return value


class ShoppingPurchase(BaseModel):
    expected_version: int = Field(ge=1)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=8)
    location: InventoryLocation
    expiration_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("quantity")
    @classmethod
    def positive_quantity(cls, value: Decimal) -> Decimal:
        return validate_purchase_amount(value)


class ShoppingMutation(BaseModel):
    expected_version: int = Field(ge=1)


class ShoppingItemResponse(BaseModel):
    id: UUID
    shopping_list_id: UUID
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    needed_amount: Decimal
    optional_amount: Decimal
    status: ShoppingItemStatus
    position: int
    notes: str | None
    purchased_amount: Decimal | None
    purchased_lot_id: UUID | None
    purchased_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ShoppingListResponse(BaseModel):
    id: UUID
    household_id: UUID
    from_date: date
    to_date: date
    state: ShoppingListState
    version: int
    items: list[ShoppingItemResponse]
    created_at: datetime
    updated_at: datetime
