from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from uribap_api.api.shopping_schemas import ShoppingListCreate, ShoppingPurchase
from uribap_api.application import shopping_service
from uribap_api.domain.inventory.ledger import InventoryLocation
from uribap_api.domain.shared.errors import DomainError
from uribap_api.domain.shopping.policies import ShoppingItemAction, ShoppingListAction
from uribap_api.mcp.runtime import McpRuntime

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)


def _current_list(session, membership):
    try:
        return shopping_service.get_current_list(session, membership)
    except DomainError as exc:
        if exc.status_code == 404:
            return None
        raise


def register(mcp: FastMCP, rt: McpRuntime) -> None:
    @mcp.tool(
        name="uribap_get_shopping_list",
        annotations=READ_ONLY.model_copy(update={"title": "Current shopping list"}),
        description=(
            "The household's active (non-archived) shopping list with every item: "
            "needed amounts, purchased/skipped state. Empty result when no list "
            "exists — create one with uribap_create_shopping_list."
        ),
    )
    def get_shopping_list(ctx: Context) -> dict[str, Any]:
        def run(session, membership, _p):
            shopping_list = _current_list(session, membership)
            if shopping_list is None:
                return {"list": None, "items": []}
            items = shopping_service.list_items(session, membership, shopping_list.id)
            return shopping_service.list_response(session, membership, shopping_list, items)

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_create_shopping_list",
        annotations=WRITE.model_copy(update={"title": "Generate shopping list"}),
        description=(
            "Generate the shopping list for a date window from the approved-plan "
            "forecast: only ingredients missing at home are included. One open "
            "list per window."
        ),
    )
    def create_shopping_list(
        ctx: Context,
        from_date: Annotated[date, Field(description="Window start, e.g. 2026-09-28")],
        to_date: Annotated[date, Field(description="Window end, e.g. 2026-10-04")],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            result = shopping_service.create_shopping_list(
                session,
                membership,
                ShoppingListCreate(from_date=from_date, to_date=to_date),
                idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_purchase_shopping_item",
        annotations=WRITE.model_copy(update={"title": "Purchase shopping item"}),
        description=(
            "Mark a list item as purchased: creates the inventory lot (stock "
            "increases immediately). `list_id` optional — the current open list "
            "is used when omitted. `unit` must equal the item unit."
        ),
    )
    def purchase_shopping_item(
        ctx: Context,
        item_id: Annotated[str, Field(description="Shopping item UUID")],
        quantity: Annotated[str, Field(description="Decimal string, e.g. '4' or '1.5'")],
        unit: Annotated[str, Field(description="Must equal the item unit")],
        location: Annotated[
            InventoryLocation, Field(description="pantry | refrigerator | freezer")
        ],
        list_id: Annotated[
            str | None, Field(description="List UUID; defaults to the current list")
        ] = None,
        expiration_date: date | None = None,
        notes: Annotated[str | None, Field(max_length=2000)] = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            shopping_list = (
                shopping_service.get_shopping_list(session, membership, UUID(list_id))
                if list_id
                else shopping_service.get_current_list(session, membership)
            )
            result = shopping_service.purchase_item(
                session,
                membership,
                shopping_list.id,
                UUID(item_id),
                ShoppingPurchase(
                    expected_version=shopping_list.version,
                    quantity=Decimal(quantity),
                    unit=unit,
                    location=location,
                    expiration_date=expiration_date,
                    notes=notes,
                ),
                idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_transition_shopping_item",
        annotations=WRITE.model_copy(update={"title": "Skip/restore shopping item"}),
        description="Skip a pending item or restore a skipped one.",
    )
    def transition_shopping_item(
        ctx: Context,
        item_id: Annotated[str, Field(description="Shopping item UUID")],
        action: Annotated[ShoppingItemAction, Field(description="skip | restore")],
        list_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            shopping_list = (
                shopping_service.get_shopping_list(session, membership, UUID(list_id))
                if list_id
                else shopping_service.get_current_list(session, membership)
            )
            result = shopping_service.transition_item(
                session,
                membership,
                shopping_list.id,
                UUID(item_id),
                action,
                expected_version=shopping_list.version,
                idempotency_key=idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_transition_shopping_list",
        annotations=WRITE.model_copy(update={"title": "Change shopping list state"}),
        description=(
            "Transition the whole list: complete (requires no pending items), "
            "reopen or archive."
        ),
    )
    def transition_shopping_list(
        ctx: Context,
        action: Annotated[
            ShoppingListAction, Field(description="complete | reopen | archive")
        ],
        list_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            shopping_list = (
                shopping_service.get_shopping_list(session, membership, UUID(list_id))
                if list_id
                else shopping_service.get_current_list(session, membership)
            )
            result = shopping_service.transition_list(
                session,
                membership,
                shopping_list.id,
                action,
                expected_version=shopping_list.version,
                idempotency_key=idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)
