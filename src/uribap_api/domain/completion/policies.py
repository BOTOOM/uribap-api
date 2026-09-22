from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from uribap_api.domain.forecast.policies import DemandForecastError, scale_factor
from uribap_api.domain.inventory.ledger import InventoryLedgerError, quantize_amount


class MealCompletionError(ValueError):
    pass


class MealCompletionState(StrEnum):
    RECORDED = "recorded"
    REOPENED = "reopened"


class MealCompletionAction(StrEnum):
    CORRECT = "correct"
    REOPEN = "reopen"


_COMPLETION_TRANSITIONS: dict[
    MealCompletionAction, tuple[frozenset[MealCompletionState], MealCompletionState]
] = {
    MealCompletionAction.CORRECT: (
        frozenset({MealCompletionState.RECORDED}),
        MealCompletionState.RECORDED,
    ),
    MealCompletionAction.REOPEN: (
        frozenset({MealCompletionState.RECORDED}),
        MealCompletionState.REOPENED,
    ),
}


def apply_completion_transition(
    state: MealCompletionState, action: MealCompletionAction
) -> MealCompletionState:
    allowed, target = _COMPLETION_TRANSITIONS[action]
    if state not in allowed:
        raise MealCompletionError(f"cannot {action} a completion in state {state}")
    return target


def assert_version(expected: int, current: int) -> int:
    if expected != current:
        raise MealCompletionError("the completion changed since it was loaded")
    return current + 1


@dataclass(frozen=True)
class RecipeIngredientInput:
    ingredient_id: UUID
    amount: Decimal
    unit: str
    optional: bool = False


@dataclass(frozen=True)
class ConsumptionLine:
    ingredient_id: UUID
    planned_amount: Decimal
    actual_amount: Decimal
    unit: str
    optional: bool


def planned_lines(
    ingredients: list[RecipeIngredientInput], servings: int, base_servings: int
) -> list[ConsumptionLine]:
    try:
        factor = scale_factor(servings, base_servings)
    except DemandForecastError as exc:
        raise MealCompletionError(str(exc)) from exc
    lines: list[ConsumptionLine] = []
    for ingredient in ingredients:
        if not ingredient.unit:
            raise MealCompletionError("ingredient unit must not be empty")
        try:
            scaled = quantize_amount(ingredient.amount * factor)
        except InventoryLedgerError as exc:
            raise MealCompletionError(str(exc)) from exc
        if scaled <= 0:
            continue
        lines.append(
            ConsumptionLine(
                ingredient_id=ingredient.ingredient_id,
                planned_amount=scaled,
                actual_amount=scaled,
                unit=ingredient.unit,
                optional=ingredient.optional,
            )
        )
    if not lines:
        raise MealCompletionError("the recipe version has no consumable ingredients")
    return lines


@dataclass(frozen=True)
class ActualLineInput:
    ingredient_id: UUID
    actual_amount: Decimal
    unit: str


def apply_actual_amounts(
    planned: list[ConsumptionLine], actuals: list[ActualLineInput]
) -> list[ConsumptionLine]:
    planned_keys = {(line.ingredient_id, line.unit) for line in planned}
    provided: dict[tuple[UUID, str], Decimal] = {}
    for actual in actuals:
        key = (actual.ingredient_id, actual.unit)
        if key not in planned_keys:
            raise MealCompletionError("actual line does not match any recipe ingredient and unit")
        if key in provided:
            raise MealCompletionError("duplicate actual line for the same ingredient")
        try:
            provided[key] = quantize_amount(actual.actual_amount, allow_zero=False)
        except InventoryLedgerError as exc:
            raise MealCompletionError(str(exc)) from exc
    lines: list[ConsumptionLine] = []
    for line in planned:
        key = (line.ingredient_id, line.unit)
        if key in provided:
            lines.append(
                ConsumptionLine(
                    ingredient_id=line.ingredient_id,
                    planned_amount=line.planned_amount,
                    actual_amount=provided[key],
                    unit=line.unit,
                    optional=line.optional,
                )
            )
        elif line.optional:
            continue
        else:
            lines.append(line)
    return lines


@dataclass(frozen=True)
class StockLot:
    lot_id: UUID
    quantity_on_hand: Decimal
    unit: str
    expiration_date: date | None


def fefo_allocate(
    lots: list[StockLot], amount: Decimal, unit: str, on_date: date
) -> list[tuple[UUID, Decimal]]:
    try:
        remaining = quantize_amount(amount, allow_zero=False)
    except InventoryLedgerError as exc:
        raise MealCompletionError(str(exc)) from exc
    eligible = [
        lot
        for lot in lots
        if lot.unit == unit
        and lot.quantity_on_hand > 0
        and (lot.expiration_date is None or lot.expiration_date >= on_date)
    ]
    eligible.sort(
        key=lambda lot: (
            lot.expiration_date is None,
            lot.expiration_date or date.max,
            str(lot.lot_id),
        )
    )
    allocation: list[tuple[UUID, Decimal]] = []
    for lot in eligible:
        if remaining <= 0:
            break
        take = min(quantize_amount(lot.quantity_on_hand), remaining)
        allocation.append((lot.lot_id, take))
        remaining = quantize_amount(remaining - take)
    if remaining > 0:
        raise MealCompletionError(f"insufficient inventory for unit {unit}: missing {remaining}")
    return allocation
