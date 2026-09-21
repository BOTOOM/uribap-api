from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from uuid import UUID

from uribap_api.domain.inventory.ledger import QUANTUM, InventoryLedgerError, quantize_amount

MAX_WINDOW_DAYS = 62


class DemandForecastError(ValueError):
    pass


def validate_window(from_date: date, to_date: date) -> tuple[date, date]:
    if from_date > to_date:
        raise DemandForecastError("from_date must be on or before to_date")
    if (to_date - from_date).days + 1 > MAX_WINDOW_DAYS:
        raise DemandForecastError(f"the projection window must not exceed {MAX_WINDOW_DAYS} days")
    return from_date, to_date


def scale_factor(servings: int, base_servings: int) -> Decimal:
    if base_servings <= 0:
        raise DemandForecastError("base_servings must be positive")
    if servings <= 0:
        raise DemandForecastError("servings must be positive")
    try:
        return (Decimal(servings) / Decimal(base_servings)).quantize(
            QUANTUM, rounding=ROUND_HALF_UP
        )
    except InvalidOperation as exc:
        raise DemandForecastError("serving scale exceeds NUMERIC(18,6) precision") from exc


@dataclass(frozen=True)
class RecipeIngredientDemand:
    ingredient_id: UUID
    amount: Decimal
    unit: str
    optional: bool = False


@dataclass(frozen=True)
class PlannedEntryDemand:
    planned_date: date
    servings: int
    base_servings: int
    ingredients: tuple[RecipeIngredientDemand, ...]


@dataclass(frozen=True)
class DemandLine:
    ingredient_id: UUID
    unit: str
    required_amount: Decimal
    optional_amount: Decimal

    @property
    def total_amount(self) -> Decimal:
        return self.required_amount + self.optional_amount


@dataclass(frozen=True)
class ProjectedLine:
    ingredient_id: UUID
    unit: str
    required_amount: Decimal
    optional_amount: Decimal
    on_hand_amount: Decimal
    shortfall_amount: Decimal

    @property
    def total_amount(self) -> Decimal:
        return self.required_amount + self.optional_amount


def _scaled(amount: Decimal, servings: int, base_servings: int) -> Decimal:
    factor = scale_factor(servings, base_servings)
    try:
        return quantize_amount(amount * factor)
    except InventoryLedgerError as exc:
        raise DemandForecastError(str(exc)) from exc


def project_demand(
    entries: list[PlannedEntryDemand], from_date: date, to_date: date
) -> list[DemandLine]:
    validate_window(from_date, to_date)
    totals: dict[tuple[UUID, str], dict[str, Decimal]] = {}
    for entry in entries:
        if not from_date <= entry.planned_date <= to_date:
            continue
        for ingredient in entry.ingredients:
            if not ingredient.unit:
                raise DemandForecastError("ingredient unit must not be empty")
            scaled = _scaled(ingredient.amount, entry.servings, entry.base_servings)
            if scaled <= 0:
                continue
            bucket = totals.setdefault(
                (ingredient.ingredient_id, ingredient.unit),
                {"required": Decimal(0), "optional": Decimal(0)},
            )
            bucket["optional" if ingredient.optional else "required"] += scaled
    lines = [
        DemandLine(
            ingredient_id=ingredient_id,
            unit=unit,
            required_amount=quantize_amount(amounts["required"]),
            optional_amount=quantize_amount(amounts["optional"]),
        )
        for (ingredient_id, unit), amounts in sorted(totals.items())
        if amounts["required"] > 0 or amounts["optional"] > 0
    ]
    return lines


def apply_on_hand(
    lines: list[DemandLine], on_hand: dict[tuple[UUID, str], Decimal]
) -> list[ProjectedLine]:
    projected: list[ProjectedLine] = []
    for line in lines:
        available = quantize_amount(on_hand.get((line.ingredient_id, line.unit), Decimal(0)))
        shortfall = line.total_amount - available
        projected.append(
            ProjectedLine(
                ingredient_id=line.ingredient_id,
                unit=line.unit,
                required_amount=line.required_amount,
                optional_amount=line.optional_amount,
                on_hand_amount=available,
                shortfall_amount=max(shortfall, Decimal(0)),
            )
        )
    return projected


@dataclass(frozen=True)
class DemandProjection:
    from_date: date
    to_date: date
    lines: tuple[ProjectedLine, ...] = field(default_factory=tuple)
