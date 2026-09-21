from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class DemandForecastLine(BaseModel):
    ingredient_id: UUID
    ingredient_name: str
    unit: str
    required_amount: Decimal
    optional_amount: Decimal
    total_amount: Decimal
    on_hand_amount: Decimal
    shortfall_amount: Decimal


class DemandForecastResponse(BaseModel):
    from_date: date
    to_date: date
    considered_plan_ids: list[UUID]
    items: list[DemandForecastLine]
