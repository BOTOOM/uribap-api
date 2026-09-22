from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from uribap_api.domain.completion.policies import (
    ActualLineInput,
    MealCompletionAction,
    MealCompletionError,
    MealCompletionState,
    RecipeIngredientInput,
    StockLot,
    apply_actual_amounts,
    apply_completion_transition,
    assert_version,
    fefo_allocate,
    planned_lines,
)


def _ingredient(
    amount: str = "0.5", unit: str = "kg", optional: bool = False
) -> RecipeIngredientInput:
    return RecipeIngredientInput(
        ingredient_id=uuid4(), amount=Decimal(amount), unit=unit, optional=optional
    )


def test_transition_reopen_from_recorded() -> None:
    assert (
        apply_completion_transition(MealCompletionState.RECORDED, MealCompletionAction.REOPEN)
        is MealCompletionState.REOPENED
    )


def test_transition_correct_keeps_recorded() -> None:
    assert (
        apply_completion_transition(MealCompletionState.RECORDED, MealCompletionAction.CORRECT)
        is MealCompletionState.RECORDED
    )


def test_transition_reopened_is_terminal() -> None:
    with pytest.raises(MealCompletionError):
        apply_completion_transition(MealCompletionState.REOPENED, MealCompletionAction.REOPEN)
    with pytest.raises(MealCompletionError):
        apply_completion_transition(MealCompletionState.REOPENED, MealCompletionAction.CORRECT)


def test_assert_version_bumps_on_match() -> None:
    assert assert_version(2, 2) == 3


def test_assert_version_rejects_stale() -> None:
    with pytest.raises(MealCompletionError):
        assert_version(1, 3)


def test_planned_lines_scale_by_servings() -> None:
    ingredient = _ingredient(amount="0.5")
    lines = planned_lines([ingredient], servings=4, base_servings=2)
    assert len(lines) == 1
    assert lines[0].planned_amount == Decimal("1.000000")
    assert lines[0].actual_amount == Decimal("1.000000")
    assert lines[0].unit == "kg"


def test_planned_lines_rejects_invalid_servings() -> None:
    with pytest.raises(MealCompletionError):
        planned_lines([_ingredient()], servings=0, base_servings=2)


def test_planned_lines_requires_consumable_ingredients() -> None:
    with pytest.raises(MealCompletionError):
        planned_lines([], servings=2, base_servings=2)


def test_planned_lines_skips_non_positive_scaled_amounts() -> None:
    tiny = _ingredient(amount="0.0000001")
    with pytest.raises(MealCompletionError):
        planned_lines([tiny], servings=2, base_servings=2)


def test_apply_actual_amounts_overrides_matching_lines() -> None:
    ingredient = _ingredient()
    lines = planned_lines([ingredient], servings=2, base_servings=2)
    updated = apply_actual_amounts(
        lines,
        [
            ActualLineInput(
                ingredient_id=ingredient.ingredient_id,
                actual_amount=Decimal("0.7"),
                unit="kg",
            )
        ],
    )
    assert updated[0].planned_amount == Decimal("0.500000")
    assert updated[0].actual_amount == Decimal("0.700000")


def test_apply_actual_amounts_drops_uncovered_optional_lines() -> None:
    required = _ingredient()
    optional = _ingredient(optional=True)
    lines = planned_lines([required, optional], servings=2, base_servings=2)
    assert len(lines) == 2
    updated = apply_actual_amounts(
        lines,
        [
            ActualLineInput(
                ingredient_id=required.ingredient_id,
                actual_amount=Decimal("0.5"),
                unit="kg",
            )
        ],
    )
    assert [line.ingredient_id for line in updated] == [required.ingredient_id]


def test_apply_actual_amounts_rejects_unknown_ingredient() -> None:
    lines = planned_lines([_ingredient()], servings=2, base_servings=2)
    with pytest.raises(MealCompletionError):
        apply_actual_amounts(
            lines,
            [ActualLineInput(uuid4(), Decimal("0.5"), "kg")],
        )


def test_apply_actual_amounts_rejects_duplicate_and_zero() -> None:
    ingredient = _ingredient()
    lines = planned_lines([ingredient], servings=2, base_servings=2)
    dup = ActualLineInput(ingredient.ingredient_id, Decimal("0.5"), "kg")
    with pytest.raises(MealCompletionError):
        apply_actual_amounts(lines, [dup, dup])
    with pytest.raises(MealCompletionError):
        apply_actual_amounts(
            lines,
            [ActualLineInput(ingredient.ingredient_id, Decimal("0"), "kg")],
        )


def _lot(quantity: str, expiration: date | None, unit: str = "kg") -> StockLot:
    return StockLot(
        lot_id=uuid4(),
        quantity_on_hand=Decimal(quantity),
        unit=unit,
        expiration_date=expiration,
    )


def test_fefo_prefers_earliest_expiration() -> None:
    later = _lot("1", date(2026, 3, 10))
    earlier = _lot("1", date(2026, 3, 5))
    allocation = fefo_allocate([later, earlier], Decimal("1.5"), "kg", date(2026, 3, 1))
    assert allocation == [
        (earlier.lot_id, Decimal("1.000000")),
        (later.lot_id, Decimal("0.500000")),
    ]


def test_fefo_null_expiration_goes_last() -> None:
    no_expiry = _lot("5", None)
    expiring = _lot("1", date(2026, 3, 5))
    allocation = fefo_allocate([no_expiry, expiring], Decimal("2"), "kg", date(2026, 3, 1))
    assert allocation[0] == (expiring.lot_id, Decimal("1.000000"))
    assert allocation[1] == (no_expiry.lot_id, Decimal("1.000000"))


def test_fefo_skips_expired_and_wrong_unit_lots() -> None:
    expired = _lot("5", date(2026, 2, 1))
    wrong_unit = _lot("5", date(2026, 3, 5), unit="l")
    good = _lot("2", date(2026, 3, 5))
    allocation = fefo_allocate([expired, wrong_unit, good], Decimal("2"), "kg", date(2026, 3, 1))
    assert allocation == [(good.lot_id, Decimal("2.000000"))]


def test_fefo_rejects_insufficient_stock() -> None:
    with pytest.raises(MealCompletionError):
        fefo_allocate([_lot("1", None)], Decimal("2"), "kg", date(2026, 3, 1))


def test_fefo_rejects_non_positive_amount() -> None:
    with pytest.raises(MealCompletionError):
        fefo_allocate([_lot("5", None)], Decimal("0"), "kg", date(2026, 3, 1))
