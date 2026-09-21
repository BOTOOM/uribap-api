from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from uribap_api.domain.planning.policies import (
    MealPlanningError,
    MealPlanState,
    validate_servings,
    validate_week_start,
)
from uribap_api.domain.recipes.policies import RecipeMealType


class MealPlanCreate(BaseModel):
    week_start_date: date

    @field_validator("week_start_date")
    @classmethod
    def monday(cls, value: date) -> date:
        try:
            return validate_week_start(value)
        except MealPlanningError as exc:
            raise ValueError(str(exc)) from exc


class MealPlanEntryCreate(BaseModel):
    expected_version: int = Field(ge=1)
    planned_date: date
    meal_type: RecipeMealType
    recipe_version_id: UUID
    servings: int
    position: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("servings")
    @classmethod
    def positive_servings(cls, value: int) -> int:
        try:
            return validate_servings(value)
        except MealPlanningError as exc:
            raise ValueError(str(exc)) from exc


class MealPlanEntryUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    planned_date: date | None = None
    meal_type: RecipeMealType | None = None
    servings: int | None = None
    position: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("servings")
    @classmethod
    def positive_servings(cls, value: int | None) -> int | None:
        if value is None:
            return value
        try:
            return validate_servings(value)
        except MealPlanningError as exc:
            raise ValueError(str(exc)) from exc


class MealPlanTransition(BaseModel):
    expected_version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=2000)


class MealPlanEntryResponse(BaseModel):
    id: UUID
    meal_plan_id: UUID
    planned_date: date
    meal_type: RecipeMealType
    recipe_version_id: UUID
    servings: int
    position: int
    notes: str | None
    added_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class MealPlanResponse(BaseModel):
    id: UUID
    household_id: UUID
    week_start_date: date
    state: MealPlanState
    version: int
    entries: list[MealPlanEntryResponse]
    created_at: datetime
    updated_at: datetime


class MealPlanStateEventResponse(BaseModel):
    id: UUID
    meal_plan_id: UUID
    from_state: MealPlanState | None
    to_state: MealPlanState
    actor_user_id: UUID
    note: str | None
    created_at: datetime


class MealPlanEventPage(BaseModel):
    items: list[MealPlanStateEventResponse]
