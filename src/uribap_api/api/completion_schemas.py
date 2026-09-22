from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from uribap_api.domain.completion.policies import MealCompletionState
from uribap_api.domain.recipes.policies import RecipeMealType


class CompletionActualLine(BaseModel):
    ingredient_id: UUID
    actual_amount: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=8)


class MealCompletionCreate(BaseModel):
    lines: list[CompletionActualLine] | None = None


class MealCompletionLineResponse(BaseModel):
    id: UUID
    ingredient_id: UUID
    ingredient_name: str | None
    planned_amount: Decimal
    actual_amount: Decimal
    unit: str
    optional: bool
    position: int


class MealCompletionResponse(BaseModel):
    id: UUID
    state: MealCompletionState
    version: int
    meal_plan_entry_id: UUID
    planned_date: date | None
    meal_type: RecipeMealType | None
    recipe_version_id: UUID | None
    recipe_name: str | None
    lines: list[MealCompletionLineResponse]
    completed_by_user_id: UUID
    completed_at: datetime
    reopened_by_user_id: UUID | None
    reopened_at: datetime | None
    reopen_reason: str | None
    created_at: datetime
    updated_at: datetime


class MealCompletionPage(BaseModel):
    items: list[MealCompletionResponse]


class MealCompletionCorrect(BaseModel):
    expected_version: int = Field(ge=1)
    actual_amount: Decimal = Field(gt=0)
    unit: str = Field(min_length=1, max_length=8)


class MealCompletionReopen(BaseModel):
    expected_version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=2000)
