from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from uribap_api.domain.planning.policies import MealPlanState
from uribap_api.domain.recipes.policies import RecipeMealType
from uribap_api.infrastructure.persistence.base import Base


def enum_values(values):
    return [item.value for item in values]


class MealPlan(Base):
    __tablename__ = "meal_plan"
    __table_args__ = (
        UniqueConstraint("id", "household_id", name="uq_meal_plan_household"),
        Index(
            "ix_meal_plan_active_week",
            "household_id",
            "week_start_date",
            unique=True,
            postgresql_where="state <> 'archived'",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    week_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[MealPlanState] = mapped_column(
        Enum(MealPlanState, native_enum=False, values_callable=enum_values),
        nullable=False,
        default=MealPlanState.DRAFT,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MealPlanEntry(Base):
    __tablename__ = "meal_plan_entry"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meal_plan_id", "household_id"],
            ["meal_plan.id", "meal_plan.household_id"],
            name="fk_meal_plan_entry_plan_household",
        ),
        UniqueConstraint(
            "meal_plan_id", "planned_date", "meal_type", "position", name="uq_meal_plan_entry_slot"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    meal_plan_id: Mapped[UUID] = mapped_column(index=True)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[RecipeMealType] = mapped_column(
        Enum(RecipeMealType, native_enum=False, values_callable=enum_values), nullable=False
    )
    recipe_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("recipe_version.id"), nullable=False
    )
    servings: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    added_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MealPlanStateEvent(Base):
    __tablename__ = "meal_plan_state_event"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meal_plan_id", "household_id"],
            ["meal_plan.id", "meal_plan.household_id"],
            name="fk_meal_plan_state_event_plan_household",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    meal_plan_id: Mapped[UUID] = mapped_column(index=True)
    from_state: Mapped[MealPlanState | None] = mapped_column(
        Enum(MealPlanState, native_enum=False, values_callable=enum_values)
    )
    to_state: Mapped[MealPlanState] = mapped_column(
        Enum(MealPlanState, native_enum=False, values_callable=enum_values), nullable=False
    )
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MealPlanOperation(Base):
    __tablename__ = "meal_plan_operation"
    __table_args__ = (
        UniqueConstraint(
            "household_id", "operation", "idempotency_key", name="uq_meal_plan_operation_idempotency"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
