from decimal import Decimal
from enum import StrEnum

from uribap_api.domain.inventory.ledger import InventoryLedgerError, quantize_amount


class ShoppingListState(StrEnum):
    OPEN = "open"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ShoppingListAction(StrEnum):
    COMPLETE = "complete"
    REOPEN = "reopen"
    ARCHIVE = "archive"


class ShoppingItemStatus(StrEnum):
    PENDING = "pending"
    PURCHASED = "purchased"
    SKIPPED = "skipped"


class ShoppingItemAction(StrEnum):
    PURCHASE = "purchase"
    SKIP = "skip"
    RESTORE = "restore"


class ShoppingError(ValueError):
    pass


_LIST_TRANSITIONS: dict[
    ShoppingListAction, tuple[frozenset[ShoppingListState], ShoppingListState]
] = {
    ShoppingListAction.COMPLETE: (
        frozenset({ShoppingListState.OPEN}),
        ShoppingListState.COMPLETED,
    ),
    ShoppingListAction.REOPEN: (
        frozenset({ShoppingListState.COMPLETED}),
        ShoppingListState.OPEN,
    ),
    ShoppingListAction.ARCHIVE: (
        frozenset({ShoppingListState.OPEN, ShoppingListState.COMPLETED}),
        ShoppingListState.ARCHIVED,
    ),
}

_ITEM_TRANSITIONS: dict[
    ShoppingItemAction, tuple[frozenset[ShoppingItemStatus], ShoppingItemStatus]
] = {
    ShoppingItemAction.PURCHASE: (
        frozenset({ShoppingItemStatus.PENDING}),
        ShoppingItemStatus.PURCHASED,
    ),
    ShoppingItemAction.SKIP: (
        frozenset({ShoppingItemStatus.PENDING}),
        ShoppingItemStatus.SKIPPED,
    ),
    ShoppingItemAction.RESTORE: (
        frozenset({ShoppingItemStatus.SKIPPED}),
        ShoppingItemStatus.PENDING,
    ),
}


def apply_list_transition(
    state: ShoppingListState, action: ShoppingListAction, *, pending_count: int
) -> ShoppingListState:
    allowed, target = _LIST_TRANSITIONS[action]
    if state not in allowed:
        raise ShoppingError(f"cannot {action} a list in state {state}")
    if action == ShoppingListAction.COMPLETE and pending_count > 0:
        raise ShoppingError("a list with pending items cannot be completed")
    return target


def apply_item_transition(
    status: ShoppingItemStatus, action: ShoppingItemAction
) -> ShoppingItemStatus:
    allowed, target = _ITEM_TRANSITIONS[action]
    if status not in allowed:
        raise ShoppingError(f"cannot {action} an item in status {status}")
    return target


def can_mutate_items(state: ShoppingListState) -> bool:
    return state == ShoppingListState.OPEN


def assert_version(expected: int, current: int) -> int:
    if expected != current:
        raise ShoppingError("the list changed since it was loaded")
    return current + 1


def validate_purchase_amount(quantity: Decimal) -> Decimal:
    try:
        return quantize_amount(quantity, allow_zero=False)
    except InventoryLedgerError as exc:
        raise ShoppingError(str(exc)) from exc


def validate_needed_amount(amount: Decimal) -> Decimal:
    try:
        return quantize_amount(amount, allow_zero=False)
    except InventoryLedgerError as exc:
        raise ShoppingError(str(exc)) from exc
