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
    ForeignKeyConstraint,
    Index,
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
    __table_args__ = (
        UniqueConstraint("id", "household_id", name="uq_inventory_lot_household"),
        Index(
            "ix_inventory_lot_positive_by_ingredient",
            "household_id",
            "ingredient_id",
            "expiration_date",
            postgresql_where="quantity_on_hand > 0 AND available IS TRUE",
        ),
    )

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
        ForeignKeyConstraint(
            ["lot_id", "household_id"],
            ["inventory_lot.id", "inventory_lot.household_id"],
            name="fk_inventory_movement_lot_household",
        ),
        UniqueConstraint(
            "household_id", "operation", "idempotency_key", name="uq_inventory_movement_idempotency"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    lot_id: Mapped[UUID] = mapped_column(index=True)
    delta: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(8), nullable=False)
    movement_type: Mapped[InventoryMovementType] = mapped_column(
        Enum(InventoryMovementType, native_enum=False, values_callable=enum_values), nullable=False
    )
    actor_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id"), nullable=False, index=True
    )
    source_type: Mapped[str | None] = mapped_column(String(80))
    source_id: Mapped[UUID | None]
    operation: Mapped[str] = mapped_column(
        String(80), nullable=False, default="inventory_adjustment"
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str | None] = mapped_column(String(64))
    result_quantity_on_hand: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
