from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.inventory_schemas import (
    InventoryAdjustment,
    InventoryLotCreate,
    InventoryLotResponse,
    InventoryMovementPage,
    InventoryMovementResponse,
    InventoryPage,
)
from uribap_api.application.inventory_service import (
    apply_adjustment,
    create_lot,
    list_lots,
    list_movements,
)
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.inventory_models import InventoryLot, InventoryMovement

router = APIRouter(prefix="/inventory", tags=["inventory"])


def lot_response(
    lot: InventoryLot, quantity_override: Decimal | None = None
) -> InventoryLotResponse:
    return InventoryLotResponse(
        id=lot.id,
        household_id=lot.household_id,
        ingredient_id=lot.ingredient_id,
        quantity_on_hand=quantity_override
        if quantity_override is not None
        else lot.quantity_on_hand,
        unit=lot.unit,
        location=lot.location,
        available=lot.available,
        expiration_date=lot.expiration_date,
        notes=lot.notes,
        updated_at=lot.updated_at,
    )


def movement_response(movement: InventoryMovement) -> InventoryMovementResponse:
    return InventoryMovementResponse(
        id=movement.id,
        lot_id=movement.lot_id,
        delta=movement.delta,
        unit=movement.unit,
        movement_type=movement.movement_type,
        actor_user_id=movement.actor_user_id,
        source_type=movement.source_type,
        source_id=movement.source_id,
        operation=movement.operation,
        idempotency_key=movement.idempotency_key,
        request_hash=movement.request_hash,
        result_quantity_on_hand=movement.result_quantity_on_hand,
        created_at=movement.created_at,
    )


@router.get("", response_model=InventoryPage)
def list_route(
    include_expired: bool = False,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> InventoryPage:
    return InventoryPage(
        items=[lot_response(lot) for lot in list_lots(session, membership, include_expired)]
    )


@router.post("/lots", response_model=InventoryLotResponse, status_code=status.HTTP_201_CREATED)
def create_lot_route(
    payload: InventoryLotCreate,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> InventoryLotResponse:
    return lot_response(create_lot(session, membership, payload))


@router.post("/adjustments", response_model=InventoryLotResponse)
def adjustment_route(
    payload: InventoryAdjustment,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> InventoryLotResponse:
    result = apply_adjustment(session, membership, payload, idempotency_key)
    return lot_response(result.lot, result.quantity_on_hand)


@router.get("/lots/{lot_id}/movements", response_model=InventoryMovementPage)
def movements_route(
    lot_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> InventoryMovementPage:
    return InventoryMovementPage(
        items=[movement_response(item) for item in list_movements(session, membership, lot_id)]
    )
