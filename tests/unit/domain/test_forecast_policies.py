from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from uribap_api.domain.forecast.policies import (
    DemandForecastError,
    PlannedEntryDemand,
    RecipeIngredientDemand,
    apply_on_hand,
    project_demand,
    scale_factor,
    validate_window,
)

FROM = date(2026, 9, 28)
TO = date(2026, 10, 4)


def ingredient(unit: str = "g", amount: str = "100", optional: bool = False):
    return RecipeIngredientDemand(
        ingredient_id=uuid4(), amount=Decimal(amount), unit=unit, optional=optional
    )


def entry(servings: int = 4, base: int = 2, day: date = FROM, items=()):
    return PlannedEntryDemand(
        planned_date=day,
        servings=servings,
        base_servings=base,
        ingredients=tuple(items),
    )


class TestValidateWindow:
    def test_rejects_inverted_window(self):
        with pytest.raises(DemandForecastError, match="on or before"):
            validate_window(TO, FROM)

    def test_rejects_window_over_62_days(self):
        with pytest.raises(DemandForecastError, match="62"):
            validate_window(FROM, date(2026, 12, 31))

    def test_accepts_boundary_window(self):
        assert validate_window(FROM, FROM) == (FROM, FROM)


class TestScaleFactor:
    def test_exact_decimal_halving(self):
        assert scale_factor(1, 2) == Decimal("0.500000")

    def test_rejects_non_positive_base(self):
        with pytest.raises(DemandForecastError, match="base_servings"):
            scale_factor(2, 0)

    def test_rejects_non_positive_servings(self):
        with pytest.raises(DemandForecastError, match="servings"):
            scale_factor(0, 4)


class TestProjectDemand:
    def test_scales_and_aggregates_same_ingredient_unit(self):
        target = uuid4()
        items = [
            RecipeIngredientDemand(target, Decimal("100"), "g"),
            RecipeIngredientDemand(target, Decimal("50"), "g"),
        ]
        # scale 4/2 = 2 -> 200 + 100 = 300
        lines = project_demand([entry(items=items)], FROM, TO)
        assert len(lines) == 1
        assert lines[0].required_amount == Decimal("300.000000")
        assert lines[0].unit == "g"

    def test_separates_units_without_conversion(self):
        target = uuid4()
        items = [
            RecipeIngredientDemand(target, Decimal("1"), "kg"),
            RecipeIngredientDemand(target, Decimal("500"), "g"),
        ]
        lines = project_demand([entry(servings=2, base=2, items=items)], FROM, TO)
        assert {(line.unit, line.required_amount) for line in lines} == {
            ("kg", Decimal("1.000000")),
            ("g", Decimal("500.000000")),
        }

    def test_splits_optional_amounts(self):
        target = uuid4()
        items = [
            RecipeIngredientDemand(target, Decimal("100"), "g"),
            RecipeIngredientDemand(target, Decimal("25"), "g", optional=True),
        ]
        lines = project_demand([entry(servings=2, base=2, items=items)], FROM, TO)
        assert lines[0].required_amount == Decimal("100.000000")
        assert lines[0].optional_amount == Decimal("25.000000")
        assert lines[0].total_amount == Decimal("125.000000")

    def test_excludes_entries_outside_window(self):
        outside = entry(day=date(2026, 10, 10), items=[ingredient()])
        inside = entry(items=[ingredient()])
        lines = project_demand([outside, inside], FROM, TO)
        assert len(lines) == 1
        assert lines[0].required_amount == Decimal("200.000000")

    def test_deterministic_ordering_and_result(self):
        a, b = uuid4(), uuid4()
        items = [
            RecipeIngredientDemand(b, Decimal("10"), "g"),
            RecipeIngredientDemand(a, Decimal("5"), "g"),
        ]
        first = project_demand([entry(items=items)], FROM, TO)
        second = project_demand([entry(items=items)], FROM, TO)
        assert first == second
        assert [line.ingredient_id for line in first] == sorted([a, b])

    def test_zero_scaled_lines_are_dropped(self):
        items = [RecipeIngredientDemand(uuid4(), Decimal("0"), "g")]
        assert project_demand([entry(items=items)], FROM, TO) == []

    def test_rejects_empty_unit(self):
        items = [RecipeIngredientDemand(uuid4(), Decimal("10"), "")]
        with pytest.raises(DemandForecastError, match="unit"):
            project_demand([entry(items=items)], FROM, TO)


def _demand_line(target, amount: str, servings: int = 4, base: int = 2):
    return project_demand(
        [
            entry(
                servings=servings,
                base=base,
                items=[RecipeIngredientDemand(target, Decimal(amount), "g")],
            )
        ],
        FROM,
        TO,
    )


class TestApplyOnHand:
    def test_shortfall_is_total_minus_on_hand(self):
        target = uuid4()
        line = _demand_line(target, "100", servings=2, base=2)
        projected = apply_on_hand(line, {(target, "g"): Decimal("30")})
        assert projected[0].on_hand_amount == Decimal("30.000000")
        assert projected[0].shortfall_amount == Decimal("70.000000")

    def test_no_negative_shortfall(self):
        target = uuid4()
        line = _demand_line(target, "10")
        projected = apply_on_hand(line, {(target, "g"): Decimal("999")})
        assert projected[0].shortfall_amount == Decimal("0.000000")

    def test_on_hand_only_counts_matching_unit(self):
        target = uuid4()
        line = _demand_line(target, "100", servings=2, base=2)
        projected = apply_on_hand(line, {(target, "kg"): Decimal("5")})
        assert projected[0].on_hand_amount == Decimal("0.000000")
        assert projected[0].shortfall_amount == Decimal("100.000000")
