from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.shopping_schemas import (
    ShoppingItemResponse,
    ShoppingListCreate,
    ShoppingListResponse,
    ShoppingPurchase,
)
from uribap_api.application.forecast_service import demand_forecast
from uribap_api.domain.inventory.ledger import InventoryMovementType
from uribap_api.domain.shared.errors import DomainError
from uribap_api.domain.shared.fingerprint import operation_fingerprint
from uribap_api.domain.shopping.policies import (
    ShoppingError,
    ShoppingItemAction,
    ShoppingItemStatus,
    ShoppingListAction,
    ShoppingListState,
    apply_item_transition,
    apply_list_transition,
    assert_version,
    can_mutate_items,
)
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import (
    InventoryLot,
    InventoryMovement,
)
from uribap_api.infrastructure.persistence.shopping_models import (
    ShoppingItem,
    ShoppingList,
    ShoppingOperation,
)


@dataclass(frozen=True)
class ShoppingMutationResult:
    payload: dict[str, Any]


def _ingredient_names(session: Session, items: list[ShoppingItem]) -> dict[UUID, str]:
    ids = [item.ingredient_id for item in items]
    if not ids:
        return {}
    return {
        row[0]: row[1]
        for row in session.execute(
            select(Ingredient.id, Ingredient.name).where(Ingredient.id.in_(ids))
        ).all()
    }


def list_items(session: Session, membership: HouseholdMember, list_id: UUID) -> list[ShoppingItem]:
    return list(
        session.scalars(
            select(ShoppingItem)
            .where(
                ShoppingItem.household_id == membership.household_id,
                ShoppingItem.shopping_list_id == list_id,
            )
            .order_by(ShoppingItem.position, ShoppingItem.id)
        )
    )


def list_response(
    session: Session,
    membership: HouseholdMember,
    shopping_list: ShoppingList,
    items: list[ShoppingItem],
) -> ShoppingListResponse:
    names = _ingredient_names(session, items)
    return ShoppingListResponse(
        id=shopping_list.id,
        household_id=shopping_list.household_id,
        from_date=shopping_list.from_date,
        to_date=shopping_list.to_date,
        state=shopping_list.state,
        version=shopping_list.version,
        items=[
            ShoppingItemResponse(
                id=item.id,
                shopping_list_id=item.shopping_list_id,
                ingredient_id=item.ingredient_id,
                ingredient_name=names.get(item.ingredient_id, ""),
                unit=item.unit,
                needed_amount=item.needed_amount,
                optional_amount=item.optional_amount,
                status=item.status,
                position=item.position,
                notes=item.notes,
                purchased_amount=item.purchased_amount,
                purchased_lot_id=item.purchased_lot_id,
                purchased_at=item.purchased_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in items
        ],
        created_at=shopping_list.created_at,
        updated_at=shopping_list.updated_at,
    )


def _list_payload(
    session: Session, membership: HouseholdMember, shopping_list: ShoppingList
) -> dict[str, Any]:
    items = list_items(session, membership, shopping_list.id)
    return list_response(session, membership, shopping_list, items).model_dump(mode="json")


def _get_list(
    session: Session, membership: HouseholdMember, list_id: UUID, lock: bool = False
) -> ShoppingList:
    statement = select(ShoppingList).where(
        ShoppingList.id == list_id,
        ShoppingList.household_id == membership.household_id,
    )
    if lock:
        statement = statement.with_for_update()
    shopping_list = session.scalar(statement)
    if shopping_list is None:
        raise DomainError(
            "not_found", "Shopping list not found", "The shopping list could not be found.", 404
        )
    return shopping_list


def _shopping_error(exc: ShoppingError) -> DomainError:
    return DomainError("conflict", "Shopping list conflict", str(exc), 409)


def _find_receipt(
    session: Session, membership: HouseholdMember, operation: str, key: str
) -> ShoppingOperation | None:
    return session.scalar(
        select(ShoppingOperation).where(
            ShoppingOperation.household_id == membership.household_id,
            ShoppingOperation.operation == operation,
            ShoppingOperation.idempotency_key == key,
        )
    )


def _check_receipt(receipt: ShoppingOperation | None, fingerprint: str) -> dict[str, Any] | None:
    if receipt is None:
        return None
    if receipt.request_hash != fingerprint:
        raise DomainError(
            "conflict",
            "Idempotency key conflict",
            "The key was already used for a different shopping operation.",
            409,
        )
    return receipt.result_payload


def _store_receipt(
    session: Session,
    membership: HouseholdMember,
    operation: str,
    key: str | None,
    fingerprint: str,
    payload: dict[str, Any],
) -> None:
    if key is None:
        return
    session.add(
        ShoppingOperation(
            household_id=membership.household_id,
            operation=operation,
            idempotency_key=key,
            request_hash=fingerprint,
            result_payload=payload,
        )
    )


def _commit_or_replay(
    session: Session,
    membership: HouseholdMember,
    operation: str,
    idempotency_key: str | None,
    fingerprint: str,
    conflict_detail: str,
) -> dict[str, Any] | None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if idempotency_key is not None:
            receipt = _find_receipt(session, membership, operation, idempotency_key)
            if receipt is not None:
                return _check_receipt(receipt, fingerprint)
        raise DomainError("conflict", "Shopping list conflict", conflict_detail, 409) from exc
    return None


def _locked_list(
    session: Session,
    membership: HouseholdMember,
    list_id: UUID,
    expected_version: int,
) -> ShoppingList:
    shopping_list = _get_list(session, membership, list_id, lock=True)
    try:
        assert_version(expected_version, shopping_list.version)
    except ShoppingError as exc:
        raise _shopping_error(exc) from exc
    return shopping_list


def _assert_items_mutable(shopping_list: ShoppingList) -> None:
    if not can_mutate_items(shopping_list.state):
        raise DomainError(
            "conflict",
            "Shopping list is not open",
            "Items can only change while the list is open.",
            409,
        )


def _get_item(
    session: Session, membership: HouseholdMember, shopping_list: ShoppingList, item_id: UUID
) -> ShoppingItem:
    item = session.scalar(
        select(ShoppingItem).where(
            ShoppingItem.id == item_id,
            ShoppingItem.shopping_list_id == shopping_list.id,
            ShoppingItem.household_id == membership.household_id,
        )
    )
    if item is None:
        raise DomainError(
            "not_found", "Shopping item not found", "The shopping item could not be found.", 404
        )
    return item


def create_shopping_list(
    session: Session,
    membership: HouseholdMember,
    payload: ShoppingListCreate,
    idempotency_key: str | None,
) -> ShoppingMutationResult:
    operation = "shopping_list_create"
    fingerprint = operation_fingerprint(
        operation,
        {"from_date": str(payload.from_date), "to_date": str(payload.to_date)},
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return ShoppingMutationResult(replay)
    forecast = demand_forecast(session, membership, payload.from_date, payload.to_date)
    shopping_list = ShoppingList(
        household_id=membership.household_id,
        from_date=payload.from_date,
        to_date=payload.to_date,
        state=ShoppingListState.OPEN,
        version=1,
        created_by_user_id=membership.user_id,
    )
    try:
        session.add(shopping_list)
        session.flush()
        position = 0
        for line in forecast.items:
            if line.shortfall_amount <= 0:
                continue
            session.add(
                ShoppingItem(
                    household_id=membership.household_id,
                    shopping_list_id=shopping_list.id,
                    ingredient_id=line.ingredient_id,
                    unit=line.unit,
                    needed_amount=line.shortfall_amount,
                    optional_amount=line.optional_amount,
                    status=ShoppingItemStatus.PENDING,
                    position=position,
                )
            )
            position += 1
        session.flush()
        result = _list_payload(session, membership, shopping_list)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "A shopping list already exists for this household and window.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Shopping list conflict",
            "A shopping list already exists for this household and window.",
            409,
        ) from exc
    if replay is not None:
        return ShoppingMutationResult(replay)
    return ShoppingMutationResult(result)


def get_shopping_list(session: Session, membership: HouseholdMember, list_id: UUID) -> ShoppingList:
    return _get_list(session, membership, list_id)


def get_current_list(session: Session, membership: HouseholdMember) -> ShoppingList:
    shopping_list = session.scalar(
        select(ShoppingList)
        .where(
            ShoppingList.household_id == membership.household_id,
            ShoppingList.state != ShoppingListState.ARCHIVED,
        )
        .order_by(ShoppingList.from_date.desc(), ShoppingList.created_at.desc())
        .limit(1)
    )
    if shopping_list is None:
        raise DomainError(
            "not_found",
            "Shopping list not found",
            "No active shopping list exists for this household.",
            404,
        )
    return shopping_list


def purchase_item(
    session: Session,
    membership: HouseholdMember,
    list_id: UUID,
    item_id: UUID,
    payload: ShoppingPurchase,
    idempotency_key: str | None,
) -> ShoppingMutationResult:
    operation = "shopping_item_purchase"
    fingerprint = operation_fingerprint(
        operation,
        {
            "list_id": str(list_id),
            "item_id": str(item_id),
            "quantity": str(payload.quantity),
            "unit": payload.unit,
            "location": payload.location.value,
            "expiration_date": str(payload.expiration_date) if payload.expiration_date else None,
            "notes": payload.notes,
            "expected_version": payload.expected_version,
        },
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return ShoppingMutationResult(replay)
    shopping_list = _locked_list(session, membership, list_id, payload.expected_version)
    _assert_items_mutable(shopping_list)
    item = _get_item(session, membership, shopping_list, item_id)
    if payload.unit != item.unit:
        raise DomainError(
            "validation_error",
            "Unit mismatch",
            "The purchased unit must equal the item unit.",
            422,
        )
    try:
        apply_item_transition(item.status, ShoppingItemAction.PURCHASE)
    except ShoppingError as exc:
        raise _shopping_error(exc) from exc
    lot = InventoryLot(
        household_id=membership.household_id,
        ingredient_id=item.ingredient_id,
        quantity_on_hand=payload.quantity,
        unit=item.unit,
        location=payload.location,
        expiration_date=payload.expiration_date,
        notes=payload.notes,
        created_by_user_id=membership.user_id,
    )
    try:
        session.add(lot)
        session.flush()
        session.add(
            InventoryMovement(
                household_id=membership.household_id,
                lot_id=lot.id,
                delta=payload.quantity,
                unit=item.unit,
                movement_type=InventoryMovementType.PURCHASE,
                actor_user_id=membership.user_id,
                source_type="shopping_item",
                source_id=item.id,
                operation=operation,
                result_quantity_on_hand=payload.quantity,
            )
        )
        item.status = ShoppingItemStatus.PURCHASED
        item.purchased_amount = payload.quantity
        item.purchased_lot_id = lot.id
        item.purchased_at = datetime.now(UTC)
        if payload.notes is not None:
            item.notes = payload.notes
        shopping_list.version += 1
        session.flush()
        result = _list_payload(session, membership, shopping_list)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The purchase conflicts with the current list state.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Shopping purchase conflict",
            "The purchase conflicts with the current list state.",
            409,
        ) from exc
    if replay is not None:
        return ShoppingMutationResult(replay)
    return ShoppingMutationResult(result)


def transition_item(
    session: Session,
    membership: HouseholdMember,
    list_id: UUID,
    item_id: UUID,
    action: ShoppingItemAction,
    expected_version: int,
    idempotency_key: str | None,
) -> ShoppingMutationResult:
    operation = f"shopping_item_{action.value}"
    fingerprint = operation_fingerprint(
        operation,
        {"list_id": str(list_id), "item_id": str(item_id), "expected_version": expected_version},
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return ShoppingMutationResult(replay)
    shopping_list = _locked_list(session, membership, list_id, expected_version)
    _assert_items_mutable(shopping_list)
    item = _get_item(session, membership, shopping_list, item_id)
    try:
        item.status = apply_item_transition(item.status, action)
    except ShoppingError as exc:
        raise _shopping_error(exc) from exc
    try:
        shopping_list.version += 1
        session.flush()
        result = _list_payload(session, membership, shopping_list)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The item transition conflicts with the current list state.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Shopping item conflict",
            "The item transition conflicts with the current list state.",
            409,
        ) from exc
    if replay is not None:
        return ShoppingMutationResult(replay)
    return ShoppingMutationResult(result)


def transition_list(
    session: Session,
    membership: HouseholdMember,
    list_id: UUID,
    action: ShoppingListAction,
    expected_version: int,
    idempotency_key: str | None,
) -> ShoppingMutationResult:
    operation = f"shopping_list_{action.value}"
    fingerprint = operation_fingerprint(
        operation, {"list_id": str(list_id), "expected_version": expected_version}
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return ShoppingMutationResult(replay)
    shopping_list = _locked_list(session, membership, list_id, expected_version)
    pending = (
        session.scalar(
            select(func.count())
            .select_from(ShoppingItem)
            .where(
                ShoppingItem.household_id == membership.household_id,
                ShoppingItem.shopping_list_id == shopping_list.id,
                ShoppingItem.status == ShoppingItemStatus.PENDING,
            )
        )
        or 0
    )
    try:
        shopping_list.state = apply_list_transition(
            shopping_list.state, action, pending_count=pending
        )
    except ShoppingError as exc:
        raise _shopping_error(exc) from exc
    try:
        shopping_list.version += 1
        session.flush()
        result = _list_payload(session, membership, shopping_list)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The transition conflicts with the current list state.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Shopping list conflict",
            "The transition conflicts with the current list state.",
            409,
        ) from exc
    if replay is not None:
        return ShoppingMutationResult(replay)
    return ShoppingMutationResult(result)
