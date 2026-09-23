from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.inventory_schemas import InventoryAdjustment, InventoryLotCreate
from uribap_api.domain.inventory.ledger import (
    InventoryMovementType,
    LedgerBalance,
)
from uribap_api.domain.shared.errors import DomainError
from uribap_api.domain.shared.fingerprint import operation_fingerprint
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import InventoryLot, InventoryMovement


@dataclass(frozen=True)
class InventoryLotResult:
    lot: InventoryLot
    quantity_on_hand: Decimal


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
    session: Session,
    membership: HouseholdMember,
    payload: InventoryLotCreate,
    idempotency_key: str | None = None,
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
    operation = "inventory_lot_create"
    fingerprint = operation_fingerprint(
        operation,
        {
            "ingredient_id": str(payload.ingredient_id),
            "quantity": str(payload.quantity),
            "unit": payload.unit,
            "location": payload.location.value,
            "expiration_date": str(payload.expiration_date),
            "notes": payload.notes,
        },
    )
    if idempotency_key:
        existing = session.scalar(
            select(InventoryMovement).where(
                InventoryMovement.household_id == membership.household_id,
                InventoryMovement.operation == operation,
                InventoryMovement.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_hash != fingerprint:
                raise DomainError(
                    "conflict",
                    "Idempotency key conflict",
                    "The key was already used for a different inventory operation.",
                    409,
                )
            return _get_lot(session, membership, existing.lot_id)
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
            movement_type=InventoryMovementType.PURCHASE,
            actor_user_id=membership.user_id,
            source_type="inventory_lot",
            operation=operation,
            idempotency_key=idempotency_key,
            request_hash=fingerprint if idempotency_key else None,
            result_quantity_on_hand=payload.quantity,
        )
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if not idempotency_key:
            raise
        existing = session.scalar(
            select(InventoryMovement).where(
                InventoryMovement.household_id == membership.household_id,
                InventoryMovement.operation == operation,
                InventoryMovement.idempotency_key == idempotency_key,
            )
        )
        if existing is None or existing.request_hash != fingerprint:
            raise DomainError(
                "conflict",
                "Idempotency key conflict",
                "The key was already used for a different inventory operation.",
                409,
            ) from exc
        return _get_lot(session, membership, existing.lot_id)
    session.refresh(lot)
    return lot


def list_lots(
    session: Session, membership: HouseholdMember, include_expired: bool
) -> list[InventoryLot]:
    statement = select(InventoryLot).where(InventoryLot.household_id == membership.household_id)
    if not include_expired:
        statement = statement.where(
            InventoryLot.available.is_(True),
            or_(
                InventoryLot.expiration_date.is_(None), InventoryLot.expiration_date >= date.today()
            ),
        )
    return list(
        session.scalars(
            statement.order_by(InventoryLot.expiration_date.nulls_last(), InventoryLot.id)
        )
    )


def _adjustment_result(
    session: Session, membership: HouseholdMember, movement: InventoryMovement
) -> InventoryLotResult:
    lot = _get_lot(session, membership, movement.lot_id)
    if movement.result_quantity_on_hand is None:
        raise DomainError(
            "conflict", "Inventory replay unavailable", "The original result is unavailable.", 409
        )
    return InventoryLotResult(lot=lot, quantity_on_hand=movement.result_quantity_on_hand)


def apply_adjustment(
    session: Session,
    membership: HouseholdMember,
    payload: InventoryAdjustment,
    idempotency_key: str | None,
) -> InventoryLotResult:
    operation = "inventory_adjustment"
    fingerprint = operation_fingerprint(
        operation,
        {
            "lot_id": str(payload.lot_id),
            "delta": str(payload.delta),
            "unit": payload.unit,
            "movement_type": payload.movement_type.value,
            "source_type": payload.source_type,
            "source_id": str(payload.source_id) if payload.source_id else None,
        },
    )
    if idempotency_key:
        existing = session.scalar(
            select(InventoryMovement).where(
                InventoryMovement.household_id == membership.household_id,
                InventoryMovement.operation == operation,
                InventoryMovement.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_hash != fingerprint:
                raise DomainError(
                    "conflict",
                    "Idempotency key conflict",
                    "The key was already used for a different inventory operation.",
                    409,
                )
            return _adjustment_result(session, membership, existing)
    lot = _get_lot(session, membership, payload.lot_id, lock=True)
    ingredient = session.get(Ingredient, lot.ingredient_id)
    if ingredient is None:
        raise DomainError(
            "not_found", "Ingredient not found", "The ingredient could not be found.", 404
        )
    _validate_ingredient_unit(ingredient, payload.unit)
    try:
        quantity = (
            LedgerBalance(Decimal(lot.quantity_on_hand), lot.unit)
            .apply(payload.delta, payload.unit)
            .amount
        )
    except ValueError as exc:
        raise DomainError("conflict", "Inventory balance conflict", str(exc), 409) from exc
    lot.quantity_on_hand = quantity
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
            operation=operation,
            idempotency_key=idempotency_key,
            request_hash=fingerprint if idempotency_key else None,
            result_quantity_on_hand=quantity,
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
                    InventoryMovement.operation == operation,
                    InventoryMovement.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                if existing.request_hash != fingerprint:
                    raise DomainError(
                        "conflict",
                        "Idempotency key conflict",
                        "The key was already used for a different inventory operation.",
                        409,
                    ) from exc
                return _adjustment_result(session, membership, existing)
        raise DomainError(
            "conflict", "Inventory adjustment conflict", "The adjustment could not be applied.", 409
        ) from exc
    session.refresh(lot)
    return InventoryLotResult(lot=lot, quantity_on_hand=quantity)


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
