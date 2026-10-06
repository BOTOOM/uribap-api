from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from uribap_api.domain.completion.policies import MealCompletionError
from uribap_api.domain.planning.entry_detail import (
    EntryDetailStockLot,
    RecipeIngredientRow,
    calculate_entry_detail_ingredients,
)


def _row(
    ingredient_id: UUID,
    amount: str,
    position: int,
    unit: str = "kg",
    optional: bool = False,
    row_id: UUID | None = None,
    pantry_staple: bool = False,
) -> RecipeIngredientRow:
    return RecipeIngredientRow(
        row_id=row_id or uuid4(),
        ingredient_id=ingredient_id,
        amount=Decimal(amount),
        unit=unit,
        optional=optional,
        position=position,
        pantry_staple=pantry_staple,
    )


def _lot(
    ingredient_id: UUID,
    quantity: str,
    expiration_date: date | None = None,
    *,
    unit: str = "kg",
    available: bool = True,
) -> EntryDetailStockLot:
    return EntryDetailStockLot(
        ingredient_id=ingredient_id,
        quantity_on_hand=Decimal(quantity),
        unit=unit,
        available=available,
        expiration_date=expiration_date,
    )


def test_detail_scales_omits_zero_and_allocates_duplicate_rows_in_order() -> None:
    ingredient_id = uuid4()
    rows = [
        _row(ingredient_id, "0.5", 2),
        _row(ingredient_id, "0.0000001", 0),
        _row(ingredient_id, "0.75", 1, optional=True),
    ]

    result = calculate_entry_detail_ingredients(
        rows,
        [_lot(ingredient_id, "1")],
        servings=2,
        base_servings=2,
        planned_date=date(2026, 3, 20),
        local_today=date(2026, 3, 1),
    )

    assert [line.position for line in result] == [1, 2]
    assert [line.required_amount for line in result] == [
        Decimal("0.750000"),
        Decimal("0.500000"),
    ]
    assert [line.on_hand_amount for line in result] == [
        Decimal("1.000000"),
        Decimal("0.250000"),
    ]
    assert result[0].optional is True
    assert [line.shortfall_amount for line in result] == [
        Decimal("0.000000"),
        Decimal("0.250000"),
    ]


def test_detail_orders_equal_positions_by_ingredient_id() -> None:
    ingredient_ids = sorted([uuid4(), uuid4()])
    rows = [_row(ingredient_ids[1], "1", 1), _row(ingredient_ids[0], "1", 1)]

    result = calculate_entry_detail_ingredients(
        rows,
        [],
        servings=2,
        base_servings=2,
        planned_date=date(2026, 3, 20),
        local_today=date(2026, 3, 1),
    )

    assert [line.ingredient_id for line in result] == ingredient_ids


def test_detail_breaks_equal_position_and_ingredient_ties_by_row_id() -> None:
    ingredient_id = uuid4()
    row_ids = sorted([uuid4(), uuid4()])
    rows = [
        _row(ingredient_id, "2", 1, row_id=row_ids[1]),
        _row(ingredient_id, "1", 1, row_id=row_ids[0]),
    ]

    result = calculate_entry_detail_ingredients(
        rows,
        [_lot(ingredient_id, "3")],
        servings=2,
        base_servings=2,
        planned_date=date(2026, 3, 20),
        local_today=date(2026, 3, 1),
    )

    assert [line.required_amount for line in result] == [
        Decimal("1.000000"),
        Decimal("2.000000"),
    ]
    assert [line.on_hand_amount for line in result] == [
        Decimal("3"),
        Decimal("2.000000"),
    ]


def test_detail_excludes_unavailable_zero_and_expired_lots() -> None:
    ingredient_id = uuid4()
    today = date(2026, 3, 10)
    planned_date = date(2026, 3, 20)
    result = calculate_entry_detail_ingredients(
        [_row(ingredient_id, "2", 0)],
        [
            _lot(ingredient_id, "1", planned_date),
            _lot(ingredient_id, "1", planned_date - timedelta(days=1)),
            _lot(ingredient_id, "10", planned_date, available=False),
            _lot(ingredient_id, "0", planned_date),
        ],
        servings=2,
        base_servings=2,
        planned_date=planned_date,
        local_today=today,
    )

    assert result[0].on_hand_amount == Decimal("1.000000")
    assert result[0].shortfall_amount == Decimal("1.000000")


def test_detail_uses_local_today_when_planned_date_is_in_the_past() -> None:
    ingredient_id = uuid4()
    today = date(2026, 3, 10)
    result = calculate_entry_detail_ingredients(
        [_row(ingredient_id, "1", 0)],
        [
            _lot(ingredient_id, "1", today - timedelta(days=1)),
            _lot(ingredient_id, "0.5", today),
        ],
        servings=2,
        base_servings=2,
        planned_date=today - timedelta(days=5),
        local_today=today,
    )

    assert result[0].on_hand_amount == Decimal("0.500000")
    assert result[0].shortfall_amount == Decimal("0.500000")


def test_detail_propagates_scale_range_errors() -> None:
    with pytest.raises(MealCompletionError, match="quantity exceeds NUMERIC\\(18,6\\) range"):
        calculate_entry_detail_ingredients(
            [_row(uuid4(), "999999999999.999999", 0)],
            [],
            servings=4,
            base_servings=2,
            planned_date=date(2026, 3, 20),
            local_today=date(2026, 3, 1),
        )


def test_detail_returns_empty_for_recipe_without_ingredients() -> None:
    assert (
        calculate_entry_detail_ingredients(
            [],
            [],
            servings=2,
            base_servings=2,
            planned_date=date(2026, 3, 20),
            local_today=date(2026, 3, 1),
        )
        == []
    )


def test_detail_staple_with_partial_stock_has_no_shortfall_or_allocation() -> None:
    staple_id = uuid4()
    rows = [
        _row(staple_id, "0.75", 0, pantry_staple=True),
        _row(staple_id, "0.75", 1, pantry_staple=True),
    ]

    result = calculate_entry_detail_ingredients(
        rows,
        [_lot(staple_id, "0.5")],
        servings=2,
        base_servings=2,
        planned_date=date(2026, 3, 20),
        local_today=date(2026, 3, 1),
    )

    assert [line.pantry_staple for line in result] == [True, True]
    assert [line.on_hand_amount for line in result] == [
        Decimal("0.500000"),
        Decimal("0.500000"),
    ]
    assert [line.shortfall_amount for line in result] == [
        Decimal("0.000000"),
        Decimal("0.000000"),
    ]


def test_detail_staple_with_no_stock_has_required_amount_shortfall() -> None:
    staple_id = uuid4()

    result = calculate_entry_detail_ingredients(
        [_row(staple_id, "0.75", 0, pantry_staple=True)],
        [],
        servings=2,
        base_servings=2,
        planned_date=date(2026, 3, 20),
        local_today=date(2026, 3, 1),
    )

    assert result[0].pantry_staple is True
    assert result[0].shortfall_amount == result[0].required_amount
