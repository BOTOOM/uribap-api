from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from uribap_api.domain.inventory.ledger import InventoryLocation, InventoryMovementType
from uribap_api.infrastructure.persistence.base import Base


def enum_values(values):
    return [item.value for item in values]


class InventoryLot(Base):
    __tablename__ = "inventory_lot"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    ingredient_id: Mapped[UUID] = mapped_column(ForeignKey("ingredient.id"), index=True)
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    location: Mapped[InventoryLocation] = mapped_column(
        Enum(InventoryLocation, native_enum=False, values_callable=enum_values), nullable=False
    )
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InventoryMovement(Base):
    __tablename__ = "inventory_movement"
    __table_args__ = (
        UniqueConstraint(
            "household_id", "idempotency_key", name="uq_inventory_movement_idempotency"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    lot_id: Mapped[UUID] = mapped_column(ForeignKey("inventory_lot.id"), index=True)
    delta: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    movement_type: Mapped[InventoryMovementType] = mapped_column(
        Enum(InventoryMovementType, native_enum=False, values_callable=enum_values), nullable=False
    )
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(80))
    source_id: Mapped[UUID | None]
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
