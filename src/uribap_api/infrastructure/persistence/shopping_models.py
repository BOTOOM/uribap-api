from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
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

from uribap_api.domain.shopping.policies import ShoppingItemStatus, ShoppingListState
from uribap_api.infrastructure.persistence.base import Base


def enum_values(values):
    return [item.value for item in values]


class ShoppingList(Base):
    __tablename__ = "shopping_list"
    __table_args__ = (
        UniqueConstraint("id", "household_id", name="uq_shopping_list_household"),
        Index(
            "ix_shopping_list_active_window",
            "household_id",
            "from_date",
            "to_date",
            unique=True,
            postgresql_where="state <> 'archived'",
        ),
        CheckConstraint("to_date >= from_date", name="ck_shopping_list_window_order"),
        CheckConstraint(
            "state IN ('open', 'completed', 'archived')", name="ck_shopping_list_state"
        ),
        CheckConstraint("version >= 1", name="ck_shopping_list_version_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    state: Mapped[ShoppingListState] = mapped_column(
        Enum(ShoppingListState, native_enum=False, values_callable=enum_values),
        nullable=False,
        default=ShoppingListState.OPEN,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShoppingItem(Base):
    __tablename__ = "shopping_item"
    __table_args__ = (
        ForeignKeyConstraint(
            ["shopping_list_id", "household_id"],
            ["shopping_list.id", "shopping_list.household_id"],
            name="fk_shopping_item_list_household",
        ),
        UniqueConstraint("shopping_list_id", "ingredient_id", "unit", name="uq_shopping_item_line"),
        CheckConstraint("needed_amount > 0", name="ck_shopping_item_needed_positive"),
        CheckConstraint("optional_amount >= 0", name="ck_shopping_item_optional_nonneg"),
        CheckConstraint(
            "purchased_amount IS NULL OR purchased_amount > 0",
            name="ck_shopping_item_purchased_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'purchased', 'skipped')", name="ck_shopping_item_status"
        ),
        CheckConstraint(
            "status <> 'purchased' OR (purchased_amount IS NOT NULL "
            "AND purchased_lot_id IS NOT NULL AND purchased_at IS NOT NULL)",
            name="ck_shopping_item_purchased_fields",
        ),
        CheckConstraint("position >= 0", name="ck_shopping_item_position_nonneg"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    shopping_list_id: Mapped[UUID] = mapped_column(index=True)
    ingredient_id: Mapped[UUID] = mapped_column(ForeignKey("ingredient.id"), index=True)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    needed_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    optional_amount: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    status: Mapped[ShoppingItemStatus] = mapped_column(
        Enum(ShoppingItemStatus, native_enum=False, values_callable=enum_values),
        nullable=False,
        default=ShoppingItemStatus.PENDING,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    purchased_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    purchased_lot_id: Mapped[UUID | None] = mapped_column(ForeignKey("inventory_lot.id"))
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShoppingOperation(Base):
    __tablename__ = "shopping_operation"
    __table_args__ = (
        UniqueConstraint(
            "household_id",
            "operation",
            "idempotency_key",
            name="uq_shopping_operation_idempotency",
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
