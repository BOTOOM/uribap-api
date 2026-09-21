from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from uribap_api.domain.ingredients.policies import (
    IngredientDimension,
    validate_unit_for_dimension,
)
from uribap_api.domain.recipes.policies import (
    RecipeVersionState,
    validate_servings,
)


class IngredientCreate(BaseModel):
    name: str
    category: str | None = None
    dimension: IngredientDimension
    base_unit: str
    package_size_amount: str | None = None
    package_size_unit: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("base_unit")
    @classmethod
    def validate_base_unit(cls, value: str, info) -> str:
        dimension = info.data.get("dimension")
        if dimension is not None:
            validate_unit_for_dimension(dimension, value)
        return value


class IngredientUpdate(BaseModel):
    name: str | None = None
    category: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value else value


class IngredientResponse(BaseModel):
    id: UUID
    household_id: UUID | None
    name: str
    normalized_name: str
    category: str | None
    dimension: IngredientDimension
    base_unit: str
    archived_at: datetime | None


class IngredientPage(BaseModel):
    items: list[IngredientResponse]
    page_info: dict[str, object]


class RecipeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    base_servings: int = Field(default=1, gt=0)
    prep_minutes: int = Field(default=0, ge=0)

    @field_validator("base_servings")
    @classmethod
    def validate_servings_value(cls, value: int) -> int:
        return validate_servings(value)


class RecipeVersionCreate(BaseModel):
    base_servings: int = Field(default=1, gt=0)
    prep_minutes: int = Field(default=0, ge=0)


class RecipePublishResponse(BaseModel):
    recipe_id: UUID
    version: int
    state: RecipeVersionState


class RecipeResponse(BaseModel):
    id: UUID
    household_id: UUID
    name: str
    description: str | None
    archived_at: datetime | None
    latest_version: int | None
    latest_state: RecipeVersionState | None


class RecipePage(BaseModel):
    items: list[RecipeResponse]
    page_info: dict[str, object]


class PublishedRecipeVersionResponse(BaseModel):
    recipe_version_id: UUID
    recipe_id: UUID
    recipe_name: str
    version_number: int
    base_servings: int
    prep_minutes: int


class PublishedRecipeVersionPage(BaseModel):
    items: list[PublishedRecipeVersionResponse]
