from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from uribap_api.domain.preparation.policies import (
    MAX_LEAD_MINUTES,
    PreparationTaskOrigin,
    PreparationTaskStatus,
    PreparationTaskType,
)
from uribap_api.domain.recipes.policies import PreparationRuleType, RecipeMealType


class PreparationTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    instruction: str | None = Field(default=None, max_length=2000)
    due_at: datetime
    ingredient_id: UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    unit: str | None = Field(default=None, min_length=1, max_length=8)

    @field_validator("due_at")
    @classmethod
    def aware_due_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("due_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def amount_unit_pair(self) -> PreparationTaskCreate:
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must be provided together")
        return self


class PreparationTaskMutation(BaseModel):
    expected_version: int = Field(ge=1)


class PreparationTaskResponse(BaseModel):
    id: UUID
    origin: PreparationTaskOrigin
    task_type: PreparationTaskType
    title: str
    instruction: str | None
    due_at: datetime
    status: PreparationTaskStatus
    version: int
    meal_plan_entry_id: UUID | None
    planned_date: date | None
    meal_type: RecipeMealType | None
    recipe_version_id: UUID | None
    recipe_name: str | None
    ingredient_id: UUID | None
    ingredient_name: str | None
    amount: Decimal | None
    unit: str | None
    completed_by_user_id: UUID | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PreparationTaskPage(BaseModel):
    items: list[PreparationTaskResponse]


class PreparationRuleCreate(BaseModel):
    rule_type: PreparationRuleType
    ingredient_id: UUID | None = None
    lead_minutes: int = Field(ge=0, le=MAX_LEAD_MINUTES)
    instruction: str = Field(min_length=1, max_length=2000)


class PreparationRuleResponse(BaseModel):
    id: UUID
    recipe_version_id: UUID
    rule_type: PreparationRuleType
    ingredient_id: UUID | None
    ingredient_name: str | None
    lead_minutes: int
    instruction: str
