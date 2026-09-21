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

from uribap_api.domain.preparation.policies import (
    PreparationTaskOrigin,
    PreparationTaskStatus,
    PreparationTaskType,
)
from uribap_api.infrastructure.persistence.base import Base


def enum_values(values):
    return [item.value for item in values]


class PreparationTask(Base):
    __tablename__ = "preparation_task"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meal_plan_entry_id", "household_id"],
            ["meal_plan_entry.id", "meal_plan_entry.household_id"],
            name="fk_preparation_task_entry_household",
        ),
        Index(
            "ix_preparation_task_derived_fingerprint",
            "household_id",
            "fingerprint",
            unique=True,
            postgresql_where="origin = 'derived'",
        ),
        Index("ix_preparation_task_due_at", "household_id", "status", "due_at"),
        CheckConstraint("origin IN ('derived', 'manual')", name="ck_preparation_task_origin"),
        CheckConstraint(
            "task_type IN ('defrost', 'soak', 'marinate', 'prepare_ahead', 'manual')",
            name="ck_preparation_task_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'completed', 'cancelled')",
            name="ck_preparation_task_status",
        ),
        CheckConstraint("version >= 1", name="ck_preparation_task_version_positive"),
        CheckConstraint("amount IS NULL OR amount > 0", name="ck_preparation_task_amount_positive"),
        CheckConstraint(
            "(amount IS NULL) = (unit IS NULL)", name="ck_preparation_task_amount_unit_pair"
        ),
        CheckConstraint(
            "origin <> 'derived' OR (fingerprint IS NOT NULL AND meal_plan_entry_id IS NOT NULL)",
            name="ck_preparation_task_derived_fields",
        ),
        CheckConstraint(
            "status <> 'completed' OR (completed_by_user_id IS NOT NULL "
            "AND completed_at IS NOT NULL)",
            name="ck_preparation_task_completed_fields",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    origin: Mapped[PreparationTaskOrigin] = mapped_column(
        Enum(PreparationTaskOrigin, native_enum=False, values_callable=enum_values),
        nullable=False,
    )
    task_type: Mapped[PreparationTaskType] = mapped_column(
        Enum(PreparationTaskType, native_enum=False, values_callable=enum_values),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instruction: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[PreparationTaskStatus] = mapped_column(
        Enum(PreparationTaskStatus, native_enum=False, values_callable=enum_values),
        nullable=False,
        default=PreparationTaskStatus.PENDING,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    meal_plan_entry_id: Mapped[UUID | None] = mapped_column(index=True)
    recipe_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("recipe_version.id"))
    ingredient_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingredient.id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unit: Mapped[str | None] = mapped_column(String(8))
    fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    completed_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PreparationOperation(Base):
    __tablename__ = "preparation_operation"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "operation",
            "idempotency_key",
            name="uq_preparation_operation_idempotency",
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
