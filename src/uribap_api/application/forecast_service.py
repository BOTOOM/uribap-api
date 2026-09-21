from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from uribap_api.api.forecast_schemas import DemandForecastLine, DemandForecastResponse
from uribap_api.domain.forecast.policies import (
    PlannedEntryDemand,
    RecipeIngredientDemand,
    apply_on_hand,
    project_demand,
    validate_window,
)
from uribap_api.domain.planning.policies import MealPlanState
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import InventoryLot
from uribap_api.infrastructure.persistence.planning_models import MealPlan, MealPlanEntry
from uribap_api.infrastructure.persistence.recipe_models import (
    RecipeVersion,
    RecipeVersionIngredient,
)


def demand_forecast(
    session: Session,
    membership: HouseholdMember,
    from_date: date,
    to_date: date,
) -> DemandForecastResponse:
    validate_window(from_date, to_date)
    household_id = membership.household_id

    plans = list(
        session.scalars(
            select(MealPlan).where(
                MealPlan.household_id == household_id,
                MealPlan.state == MealPlanState.APPROVED,
                MealPlan.week_start_date <= to_date,
                MealPlan.week_start_date >= from_date - timedelta(days=6),
            )
        )
    )
    plan_ids = sorted(plan.id for plan in plans)
    if not plan_ids:
        return DemandForecastResponse(
            from_date=from_date, to_date=to_date, considered_plan_ids=[], items=[]
        )

    entries = list(
        session.scalars(
            select(MealPlanEntry).where(
                MealPlanEntry.household_id == household_id,
                MealPlanEntry.meal_plan_id.in_(plan_ids),
                MealPlanEntry.planned_date >= from_date,
                MealPlanEntry.planned_date <= to_date,
            )
        )
    )
    version_ids = sorted({entry.recipe_version_id for entry in entries})
    base_servings = {
        row[0]: row[1]
        for row in session.execute(
            select(RecipeVersion.id, RecipeVersion.base_servings).where(
                RecipeVersion.id.in_(version_ids)
            )
        ).all()
    }
    ingredient_rows = (
        session.execute(
            select(
                RecipeVersionIngredient.recipe_version_id,
                RecipeVersionIngredient.ingredient_id,
                RecipeVersionIngredient.amount,
                RecipeVersionIngredient.unit,
                RecipeVersionIngredient.optional,
            ).where(RecipeVersionIngredient.recipe_version_id.in_(version_ids))
        ).all()
        if version_ids
        else []
    )
    ingredients_by_version: dict[UUID, list[RecipeIngredientDemand]] = {}
    for version_id, ingredient_id, amount, unit, optional in ingredient_rows:
        ingredients_by_version.setdefault(version_id, []).append(
            RecipeIngredientDemand(
                ingredient_id=ingredient_id,
                amount=Decimal(amount),
                unit=unit,
                optional=optional,
            )
        )

    planned = [
        PlannedEntryDemand(
            planned_date=entry.planned_date,
            servings=entry.servings,
            base_servings=base_servings[entry.recipe_version_id],
            ingredients=tuple(ingredients_by_version.get(entry.recipe_version_id, [])),
        )
        for entry in entries
    ]
    lines = project_demand(planned, from_date, to_date)

    on_hand: dict[tuple[UUID, str], Decimal] = {}
    for ingredient_id, unit, total in session.execute(
        select(
            InventoryLot.ingredient_id,
            InventoryLot.unit,
            func.sum(InventoryLot.quantity_on_hand),
        )
        .where(
            InventoryLot.household_id == household_id,
            InventoryLot.available.is_(True),
            InventoryLot.quantity_on_hand > 0,
            (InventoryLot.expiration_date.is_(None)) | (InventoryLot.expiration_date >= from_date),
        )
        .group_by(InventoryLot.ingredient_id, InventoryLot.unit)
    ):
        on_hand[(ingredient_id, unit)] = Decimal(total)

    projected = apply_on_hand(lines, on_hand)

    names = {
        row[0]: row[1]
        for row in session.execute(
            select(Ingredient.id, Ingredient.name).where(
                Ingredient.id.in_([line.ingredient_id for line in projected])
            )
        ).all()
    }
    items = sorted(
        (
            DemandForecastLine(
                ingredient_id=line.ingredient_id,
                ingredient_name=names.get(line.ingredient_id, ""),
                unit=line.unit,
                required_amount=line.required_amount,
                optional_amount=line.optional_amount,
                total_amount=line.total_amount,
                on_hand_amount=line.on_hand_amount,
                shortfall_amount=line.shortfall_amount,
            )
            for line in projected
        ),
        key=lambda item: (item.ingredient_name.casefold(), item.unit, item.ingredient_id),
    )
    return DemandForecastResponse(
        from_date=from_date,
        to_date=to_date,
        considered_plan_ids=plan_ids,
        items=items,
    )
