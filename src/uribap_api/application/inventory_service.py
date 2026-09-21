from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.inventory_schemas import InventoryAdjustment, InventoryLotCreate
from uribap_api.domain.inventory.ledger import LedgerBalance
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import InventoryLot, InventoryMovement


def _validate_ingredient_unit(ingredient: Ingredient, unit: str) -> None:
    from uribap_api.domain.ingredients.policies import validate_unit_for_dimension

    try:
        validate_unit_for_dimension(ingredient.dimension, unit)
    except ValueError as exc:
        raise DomainError("validation_error", "Invalid inventory unit", str(exc), 422) from exc


def _get_lot(
    session: Session, membership: HouseholdMember, lot_id: UUID, lock: bool = False
) -> InventoryLot:
    statement = select(InventoryLot).where(
        InventoryLot.id == lot_id,
        InventoryLot.household_id == membership.household_id,
    )
    if lock:
        statement = statement.with_for_update()
    lot = session.scalar(statement)
    if lot is None:
        raise DomainError(
            "not_found", "Inventory lot not found", "The inventory lot could not be found.", 404
        )
    return lot


def create_lot(
    session: Session, membership: HouseholdMember, payload: InventoryLotCreate
) -> InventoryLot:
    ingredient = session.get(Ingredient, payload.ingredient_id)
    if ingredient is None or ingredient.archived_at is not None:
        raise DomainError(
            "not_found", "Ingredient not found", "The ingredient could not be found.", 404
        )
    if ingredient.household_id not in {None, membership.household_id}:
        raise DomainError(
            "forbidden",
            "Permission denied",
            "The ingredient is not available to this household.",
            403,
        )
    _validate_ingredient_unit(ingredient, payload.unit)
    lot = InventoryLot(
        household_id=membership.household_id,
        ingredient_id=payload.ingredient_id,
        quantity_on_hand=payload.quantity,
        unit=payload.unit,
        location=payload.location,
        expiration_date=payload.expiration_date,
        notes=payload.notes,
        created_by_user_id=membership.user_id,
    )
    session.add(lot)
    session.flush()
    session.add(
        InventoryMovement(
            household_id=membership.household_id,
            lot_id=lot.id,
            delta=payload.quantity,
            unit=payload.unit,
            movement_type="purchase",
            actor_user_id=membership.user_id,
            source_type="inventory_lot",
        )
    )
    session.commit()
    session.refresh(lot)
    return lot


def list_lots(
    session: Session, membership: HouseholdMember, include_expired: bool
) -> list[InventoryLot]:
    statement = select(InventoryLot).where(InventoryLot.household_id == membership.household_id)
    if not include_expired:
        statement = statement.where(InventoryLot.available.is_(True))
    return list(
        session.scalars(
            statement.order_by(InventoryLot.expiration_date.nulls_last(), InventoryLot.id)
        )
    )


def apply_adjustment(
    session: Session,
    membership: HouseholdMember,
    payload: InventoryAdjustment,
    idempotency_key: str | None,
) -> InventoryLot:
    if idempotency_key:
        existing = session.scalar(
            select(InventoryMovement).where(
                InventoryMovement.household_id == membership.household_id,
                InventoryMovement.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return _get_lot(session, membership, existing.lot_id)
    lot = _get_lot(session, membership, payload.lot_id, lock=True)
    ingredient = session.get(Ingredient, lot.ingredient_id)
    if ingredient is None:
        raise DomainError(
            "not_found", "Ingredient not found", "The ingredient could not be found.", 404
        )
    _validate_ingredient_unit(ingredient, payload.unit)
    try:
        lot.quantity_on_hand = (
            LedgerBalance(Decimal(lot.quantity_on_hand), lot.unit)
            .apply(payload.delta, payload.unit)
            .amount
        )
    except ValueError as exc:
        raise DomainError("conflict", "Inventory balance conflict", str(exc), 409) from exc
    session.add(
        InventoryMovement(
            household_id=membership.household_id,
            lot_id=lot.id,
            delta=payload.delta,
            unit=payload.unit,
            movement_type=payload.movement_type,
            actor_user_id=membership.user_id,
            source_type=payload.source_type,
            source_id=payload.source_id,
            idempotency_key=idempotency_key,
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if idempotency_key:
            existing = session.scalar(
                select(InventoryMovement).where(
                    InventoryMovement.household_id == membership.household_id,
                    InventoryMovement.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return _get_lot(session, membership, existing.lot_id)
        raise DomainError(
            "conflict", "Inventory adjustment conflict", "The adjustment could not be applied.", 409
        ) from exc
    session.refresh(lot)
    return lot


def list_movements(
    session: Session, membership: HouseholdMember, lot_id: UUID
) -> list[InventoryMovement]:
    _get_lot(session, membership, lot_id)
    return list(
        session.scalars(
            select(InventoryMovement)
            .where(
                InventoryMovement.household_id == membership.household_id,
                InventoryMovement.lot_id == lot_id,
            )
            .order_by(InventoryMovement.created_at, InventoryMovement.id)
        )
    )
