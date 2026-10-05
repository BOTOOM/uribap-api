from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from uribap_api.domain.completion.policies import (
    RecipeIngredientInput,
    scale_recipe_ingredient,
)


@dataclass(frozen=True)
class RecipeIngredientRow:
    row_id: UUID
    ingredient_id: UUID
    amount: Decimal
    unit: str
    optional: bool
    position: int


@dataclass(frozen=True)
class EntryDetailStockLot:
    ingredient_id: UUID
    quantity_on_hand: Decimal
    unit: str
    available: bool
    expiration_date: date | None


@dataclass(frozen=True)
class EntryDetailIngredient:
    ingredient_id: UUID
    required_amount: Decimal
    unit: str
    optional: bool
    on_hand_amount: Decimal
    shortfall_amount: Decimal
    position: int


def calculate_entry_detail_ingredients(
    recipe_ingredients: list[RecipeIngredientRow],
    stock_lots: list[EntryDetailStockLot],
    *,
    servings: int,
    base_servings: int,
    planned_date: date,
    local_today: date,
) -> list[EntryDetailIngredient]:
    reference_date = max(local_today, planned_date)
    remaining_stock: dict[tuple[UUID, str], Decimal] = {}
    for lot in stock_lots:
        if (
            not lot.available
            or lot.quantity_on_hand <= 0
            or (lot.expiration_date is not None and lot.expiration_date < reference_date)
        ):
            continue
        key = (lot.ingredient_id, lot.unit)
        remaining_stock[key] = remaining_stock.get(key, Decimal("0")) + lot.quantity_on_hand

    projected: list[EntryDetailIngredient] = []
    for row in sorted(
        recipe_ingredients,
        key=lambda item: (item.position, item.ingredient_id, item.row_id),
    ):
        line = scale_recipe_ingredient(
            RecipeIngredientInput(
                ingredient_id=row.ingredient_id,
                amount=row.amount,
                unit=row.unit,
                optional=row.optional,
            ),
            servings,
            base_servings,
        )
        if line is None:
            continue
        key = (line.ingredient_id, line.unit)
        remaining = remaining_stock.get(key, Decimal("0"))
        projected.append(
            EntryDetailIngredient(
                ingredient_id=line.ingredient_id,
                required_amount=line.planned_amount,
                unit=line.unit,
                optional=line.optional,
                on_hand_amount=remaining,
                shortfall_amount=max(Decimal("0"), line.planned_amount - remaining),
                position=row.position,
            )
        )
        remaining_stock[key] = remaining - min(line.planned_amount, remaining)
    return projected
