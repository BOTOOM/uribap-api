from decimal import Decimal

import pytest

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
    validate_needed_amount,
    validate_purchase_amount,
)


class TestListTransitions:
    def test_open_to_completed_requires_zero_pending(self):
        with pytest.raises(ShoppingError, match="pending"):
            apply_list_transition(
                ShoppingListState.OPEN, ShoppingListAction.COMPLETE, pending_count=2
            )
        assert (
            apply_list_transition(
                ShoppingListState.OPEN, ShoppingListAction.COMPLETE, pending_count=0
            )
            == ShoppingListState.COMPLETED
        )

    def test_completed_reopens_to_open(self):
        assert (
            apply_list_transition(
                ShoppingListState.COMPLETED, ShoppingListAction.REOPEN, pending_count=0
            )
            == ShoppingListState.OPEN
        )

    def test_archive_from_open_or_completed_terminal(self):
        assert (
            apply_list_transition(
                ShoppingListState.OPEN, ShoppingListAction.ARCHIVE, pending_count=3
            )
            == ShoppingListState.ARCHIVED
        )
        with pytest.raises(ShoppingError, match="archived"):
            apply_list_transition(
                ShoppingListState.ARCHIVED, ShoppingListAction.ARCHIVE, pending_count=0
            )
        with pytest.raises(ShoppingError):
            apply_list_transition(
                ShoppingListState.ARCHIVED, ShoppingListAction.REOPEN, pending_count=0
            )

    def test_complete_not_allowed_from_completed(self):
        with pytest.raises(ShoppingError):
            apply_list_transition(
                ShoppingListState.COMPLETED, ShoppingListAction.COMPLETE, pending_count=0
            )


class TestItemTransitions:
    def test_pending_purchase_and_skip(self):
        assert (
            apply_item_transition(ShoppingItemStatus.PENDING, ShoppingItemAction.PURCHASE)
            == ShoppingItemStatus.PURCHASED
        )
        assert (
            apply_item_transition(ShoppingItemStatus.PENDING, ShoppingItemAction.SKIP)
            == ShoppingItemStatus.SKIPPED
        )

    def test_skipped_restores_to_pending(self):
        assert (
            apply_item_transition(ShoppingItemStatus.SKIPPED, ShoppingItemAction.RESTORE)
            == ShoppingItemStatus.PENDING
        )

    def test_purchased_is_terminal(self):
        for action in ShoppingItemAction:
            with pytest.raises(ShoppingError):
                apply_item_transition(ShoppingItemStatus.PURCHASED, action)

    def test_pending_cannot_restore(self):
        with pytest.raises(ShoppingError):
            apply_item_transition(ShoppingItemStatus.PENDING, ShoppingItemAction.RESTORE)


class TestVersionAndAmounts:
    def test_version_bumps_or_conflicts(self):
        assert assert_version(3, 3) == 4
        with pytest.raises(ShoppingError, match="changed"):
            assert_version(2, 3)

    def test_items_mutable_only_when_open(self):
        assert can_mutate_items(ShoppingListState.OPEN) is True
        for state in (ShoppingListState.COMPLETED, ShoppingListState.ARCHIVED):
            assert can_mutate_items(state) is False

    def test_purchase_amount_positive_quantized(self):
        assert validate_purchase_amount(Decimal("1.5")) == Decimal("1.500000")
        with pytest.raises(ShoppingError):
            validate_purchase_amount(Decimal("0"))
        with pytest.raises(ShoppingError):
            validate_purchase_amount(Decimal("-2"))

    def test_needed_amount_positive(self):
        assert validate_needed_amount(Decimal("0.5")) == Decimal("0.500000")
        with pytest.raises(ShoppingError):
            validate_needed_amount(Decimal("0"))
