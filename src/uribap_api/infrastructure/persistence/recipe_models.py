from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from uribap_api.domain.recipes.policies import (
    PreparationRuleType,
    RecipeVersionState,
)
from uribap_api.domain.recipes.policies import (
    RecipeMealType as RecipeMealTypeValue,
)
from uribap_api.infrastructure.persistence.base import Base


def enum_values(values):
    return [item.value for item in values]


class Recipe(Base):
    __tablename__ = "recipe"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RecipeVersion(Base):
    __tablename__ = "recipe_version"
    __table_args__ = (
        UniqueConstraint("recipe_id", "version_number", name="uq_recipe_version_number"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipe.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    base_servings: Mapped[int] = mapped_column(Integer, nullable=False)
    prep_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[RecipeVersionState] = mapped_column(
        Enum(RecipeVersionState, native_enum=False, values_callable=enum_values),
        nullable=False,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    published_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RecipeVersionIngredient(Base):
    __tablename__ = "recipe_version_ingredient"
    __table_args__ = (
        Index("ix_recipe_version_ingredient_version", "recipe_version_id"),
        Index("ix_recipe_version_ingredient_ingredient", "ingredient_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipe_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipe_version.id", ondelete="CASCADE")
    )
    ingredient_id: Mapped[UUID] = mapped_column(ForeignKey("ingredient.id"))
    amount: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    optional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RecipeInstruction(Base):
    __tablename__ = "recipe_instruction"
    __table_args__ = (
        UniqueConstraint("recipe_version_id", "position", name="uq_recipe_instruction_position"),
        Index("ix_recipe_instruction_version", "recipe_version_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipe_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipe_version.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class RecipeMealTypeRow(Base):
    __tablename__ = "recipe_meal_type"
    __table_args__ = (
        UniqueConstraint("recipe_version_id", "meal_type", name="uq_recipe_meal_type"),
        Index("ix_recipe_meal_type_version", "recipe_version_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipe_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipe_version.id", ondelete="CASCADE")
    )
    meal_type: Mapped[RecipeMealTypeValue] = mapped_column(
        Enum(RecipeMealTypeValue, native_enum=False, values_callable=enum_values), nullable=False
    )


class RecipeTag(Base):
    __tablename__ = "recipe_tag"
    __table_args__ = (
        UniqueConstraint("household_id", "normalized_name", name="uq_recipe_tag_name"),
        Index("ix_recipe_tag_household_id", "household_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(ForeignKey("household.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(80), nullable=False)


class RecipeTagLink(Base):
    __tablename__ = "recipe_tag_link"
    __table_args__ = (
        UniqueConstraint("recipe_version_id", "tag_id", name="uq_recipe_tag_link"),
        Index("ix_recipe_tag_link_version", "recipe_version_id"),
        Index("ix_recipe_tag_link_tag", "tag_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipe_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipe_version.id", ondelete="CASCADE")
    )
    tag_id: Mapped[UUID] = mapped_column(ForeignKey("recipe_tag.id", ondelete="CASCADE"))


class RecipeFavorite(Base):
    __tablename__ = "recipe_favorite"
    __table_args__ = (
        UniqueConstraint("user_id", "recipe_id", name="uq_recipe_favorite"),
        Index("ix_recipe_favorite_user_id", "user_id"),
        Index("ix_recipe_favorite_recipe_id", "recipe_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    recipe_id: Mapped[UUID] = mapped_column(ForeignKey("recipe.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecipePreparationRule(Base):
    __tablename__ = "recipe_preparation_rule"
    __table_args__ = (Index("ix_recipe_prep_rule_version", "recipe_version_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recipe_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipe_version.id", ondelete="CASCADE")
    )
    rule_type: Mapped[PreparationRuleType] = mapped_column(
        Enum(PreparationRuleType, native_enum=False, values_callable=enum_values), nullable=False
    )
    ingredient_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingredient.id"))
    lead_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
