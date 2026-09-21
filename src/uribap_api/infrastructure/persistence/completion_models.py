from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from uribap_api.domain.completion.policies import MealCompletionState
from uribap_api.infrastructure.persistence.base import Base


def enum_values(values):
    return [item.value for item in values]


class MealCompletion(Base):
    __tablename__ = "meal_completion"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meal_plan_entry_id", "household_id"],
            ["meal_plan_entry.id", "meal_plan_entry.household_id"],
            name="fk_meal_completion_entry_household",
        ),
        UniqueConstraint("id", "household_id", name="uq_meal_completion_household"),
        Index(
            "ix_meal_completion_recorded_entry",
            "household_id",
            "meal_plan_entry_id",
            unique=True,
            postgresql_where="state = 'recorded'",
        ),
        Index("ix_meal_completion_completed_at", "household_id", "completed_at"),
        CheckConstraint(
            "state IN ('recorded', 'reopened')", name="ck_meal_completion_state"
        ),
        CheckConstraint("version >= 1", name="ck_meal_completion_version_positive"),
        CheckConstraint(
            "state <> 'reopened' OR (reopened_by_user_id IS NOT NULL "
            "AND reopened_at IS NOT NULL)",
            name="ck_meal_completion_reopened_fields",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    meal_plan_entry_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    state: Mapped[MealCompletionState] = mapped_column(
        Enum(MealCompletionState, native_enum=False, values_callable=enum_values),
        nullable=False,
        default=MealCompletionState.RECORDED,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id"), nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reopened_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopen_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MealCompletionLine(Base):
    __tablename__ = "meal_completion_line"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meal_completion_id", "household_id"],
            ["meal_completion.id", "meal_completion.household_id"],
            name="fk_meal_completion_line_completion_household",
        ),
        UniqueConstraint(
            "meal_completion_id",
            "ingredient_id",
            "unit",
            name="uq_meal_completion_line_ingredient",
        ),
        CheckConstraint(
            "planned_amount >= 0", name="ck_meal_completion_line_planned_nonneg"
        ),
        CheckConstraint(
            "actual_amount > 0", name="ck_meal_completion_line_actual_positive"
        ),
        CheckConstraint(
            "length(btrim(unit)) > 0", name="ck_meal_completion_line_unit_nonempty"
        ),
        CheckConstraint(
            "position >= 0", name="ck_meal_completion_line_position_nonneg"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    meal_completion_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    ingredient_id: Mapped[UUID] = mapped_column(
        ForeignKey("ingredient.id"), nullable=False
    )
    planned_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    optional: Mapped[bool] = mapped_column(nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CompletionOperation(Base):
    __tablename__ = "completion_operation"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "operation",
            "idempotency_key",
            name="uq_completion_operation_idempotency",
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
