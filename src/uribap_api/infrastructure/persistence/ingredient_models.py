from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.infrastructure.persistence.base import Base


class Ingredient(Base):
    __tablename__ = "ingredient"
    __table_args__ = (
        Index(
            "uq_ingredient_global_normalized_name",
            "normalized_name",
            unique=True,
            postgresql_where="household_id IS NULL AND archived_at IS NULL",
        ),
        Index(
            "uq_ingredient_household_normalized_name",
            "household_id",
            "normalized_name",
            unique=True,
            postgresql_where="archived_at IS NULL",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID | None] = mapped_column(ForeignKey("household.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80))
    dimension: Mapped[IngredientDimension] = mapped_column(
        Enum(
            IngredientDimension,
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
    )
    base_unit: Mapped[str] = mapped_column(String(8), nullable=False)
    package_size_amount: Mapped[float | None] = mapped_column(Numeric(18, 6))
    package_size_unit: Mapped[str | None] = mapped_column(String(8))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
