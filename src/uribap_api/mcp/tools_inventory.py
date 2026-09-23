from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field
from sqlalchemy import select

from uribap_api.api.inventory_schemas import InventoryAdjustment, InventoryLotCreate
from uribap_api.application import forecast_service, inventory_service
from uribap_api.domain.inventory.ledger import InventoryLocation, InventoryMovementType
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.mcp.runtime import McpRuntime

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)


def _lot_row(lot, ingredient_name: str | None) -> dict:
    return {
        "lot_id": str(lot.id),
        "ingredient_id": str(lot.ingredient_id),
        "ingredient_name": ingredient_name,
        "quantity_on_hand": lot.quantity_on_hand,
        "unit": lot.unit,
        "location": lot.location.value,
        "available": lot.available,
        "expiration_date": lot.expiration_date,
        "notes": lot.notes,
        "created_at": lot.created_at,
    }


def register(mcp: FastMCP, rt: McpRuntime) -> None:
    @mcp.tool(
        name="uribap_get_inventory",
        annotations=READ_ONLY.model_copy(update={"title": "Current inventory"}),
        description=(
            "Real stock on hand: every usable lot with ingredient, quantity, "
            "location and expiration. Set include_expired=true to see all lots."
        ),
    )
    def get_inventory(
        ctx: Context,
        include_expired: Annotated[
            bool, Field(description="Include expired or depleted lots")
        ] = False,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            lots = inventory_service.list_lots(session, membership, include_expired)
            names = {
                row[0]: row[1]
                for row in session.execute(
                    select(Ingredient.id, Ingredient.name).where(
                        Ingredient.id.in_({lot.ingredient_id for lot in lots})
                    )
                ).all()
            } if lots else {}
            return {
                "count": len(lots),
                "lots": [_lot_row(lot, names.get(lot.ingredient_id)) for lot in lots],
            }

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_list_movements",
        annotations=READ_ONLY.model_copy(update={"title": "Lot movement ledger"}),
        description="Movement history (purchases, adjustments, consumption) of one lot.",
    )
    def list_movements(
        ctx: Context,
        lot_id: Annotated[str, Field(description="Inventory lot UUID")],
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            return {
                "movements": [
                    {
                        "id": str(mv.id),
                        "delta": mv.delta,
                        "unit": mv.unit,
                        "movement_type": mv.movement_type.value,
                        "result_quantity_on_hand": mv.result_quantity_on_hand,
                        "actor_user_id": mv.actor_user_id,
                        "source_type": mv.source_type,
                        "created_at": mv.created_at,
                    }
                    for mv in inventory_service.list_movements(
                        session, membership, UUID(lot_id)
                    )
                ]
            }

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_get_forecast",
        annotations=READ_ONLY.model_copy(update={"title": "Demand forecast"}),
        description=(
            "Projected ingredient demand from APPROVED plans inside a date window "
            "(YYYY-MM-DD). Returns required vs on-hand amounts and the shortfall "
            "the shopping list would contain."
        ),
    )
    def get_forecast(
        ctx: Context,
        from_date: Annotated[date, Field(description="Window start, e.g. 2026-09-28")],
        to_date: Annotated[date, Field(description="Window end, e.g. 2026-10-04")],
    ) -> dict[str, Any]:
        return rt.call(
            ctx,
            lambda session, membership, _p: forecast_service.demand_forecast(
                session, membership, from_date, to_date
            ),
        )

    @mcp.tool(
        name="uribap_register_purchase",
        annotations=WRITE.model_copy(update={"title": "Register purchase lot"}),
        description=(
            "Register a new inventory lot (what a user does when they buy food). "
            "unit must match the ingredient base unit; location is pantry | "
            "refrigerator | freezer."
        ),
    )
    def register_purchase(
        ctx: Context,
        ingredient_id: Annotated[str, Field(description="Ingredient UUID")],
        quantity: Annotated[str, Field(description="Decimal string, e.g. '500' or '2.5'")],
        unit: Annotated[str, Field(description="unit | g | kg | ml | l")],
        location: Annotated[
            InventoryLocation, Field(description="pantry | refrigerator | freezer")
        ],
        expiration_date: Annotated[
            date | None, Field(description="Optional best-before date")
        ] = None,
        notes: Annotated[str | None, Field(max_length=2000)] = None,
        idempotency_key: Annotated[
            str | None,
            Field(description="Optional key to deduplicate retries; generated if omitted"),
        ] = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            lot = inventory_service.create_lot(
                session,
                membership,
                InventoryLotCreate(
                    ingredient_id=UUID(ingredient_id),
                    quantity=Decimal(quantity),
                    unit=unit,
                    location=location,
                    expiration_date=expiration_date,
                    notes=notes,
                ),
                idempotency_key or str(uuid4()),
            )
            ingredient = session.get(Ingredient, lot.ingredient_id)
            return _lot_row(lot, ingredient.name if ingredient else None)

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_adjust_lot",
        annotations=WRITE.model_copy(update={"title": "Adjust lot quantity"}),
        description=(
            "Correct the real balance of a lot: `delta` may be negative (remove) "
            "or positive (add). Every adjustment is recorded in the ledger. "
            "movement_type: manual_adjustment | waste | purchase | reversal."
        ),
    )
    def adjust_lot(
        ctx: Context,
        lot_id: Annotated[str, Field(description="Inventory lot UUID")],
        delta: Annotated[str, Field(description="Signed decimal, e.g. '-200' or '50'")],
        unit: Annotated[str, Field(description="Unit matching the lot unit")],
        movement_type: Annotated[
            InventoryMovementType,
            Field(description="manual_adjustment | waste | purchase | reversal"),
        ] = InventoryMovementType.MANUAL_ADJUSTMENT,
        idempotency_key: Annotated[
            str | None,
            Field(description="Optional key to deduplicate retries; generated if omitted"),
        ] = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            result = inventory_service.apply_adjustment(
                session,
                membership,
                InventoryAdjustment(
                    lot_id=UUID(lot_id),
                    delta=Decimal(delta),
                    unit=unit,
                    movement_type=movement_type,
                    source_type="mcp_agent",
                ),
                idempotency_key or str(uuid4()),
            )
            return {
                "lot_id": str(result.lot.id),
                "quantity_on_hand": result.quantity_on_hand,
                "unit": result.lot.unit,
                "available": result.lot.available,
            }

        return rt.call(ctx, run)
