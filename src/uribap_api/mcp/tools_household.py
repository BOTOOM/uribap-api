from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from uribap_api.api.schemas import HouseholdUpdate
from uribap_api.application import event_service, household_service
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.mcp.runtime import McpRuntime

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)


def register(mcp: FastMCP, rt: McpRuntime) -> None:
    @mcp.tool(
        name="uribap_get_context",
        annotations=READ_ONLY.model_copy(update={"title": "Who am I"}),
        description=(
            "Return the authenticated user, household and role behind this MCP token. "
            "Call this first to learn household_id and confirm access."
        ),
    )
    def get_context(ctx: Context) -> dict[str, Any]:
        def run(session, membership, principal):
            household = household_service.get_household(session, principal.household_id)
            return {
                "user_id": str(principal.user_id),
                "display_name": principal.display_name,
                "email": principal.email,
                "role": principal.role,
                "household": {
                    "id": str(household.id),
                    "name": household.name,
                    "locale": household.locale,
                    "timezone": household.timezone,
                    "version": household.version,
                },
            }

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_list_members",
        annotations=READ_ONLY.model_copy(update={"title": "List household members"}),
        description="List the active members of the household with their roles.",
    )
    def list_members(ctx: Context) -> dict[str, Any]:
        return rt.call(
            ctx,
            lambda session, membership, _p: [
                {
                    "user_id": str(member.user_id),
                    "role": member.role.value,
                    "status": member.status.value,
                    "display_name": user.display_name,
                    "email": user.email,
                }
                for member, user in household_service.list_members(
                    session, membership.household_id, limit=50
                )
            ],
        )

    @mcp.tool(
        name="uribap_update_household",
        annotations=WRITE.model_copy(update={"title": "Update household settings"}),
        description="Rename the household or change its locale/timezone.",
    )
    def update_household(
        ctx: Context,
        name: Annotated[str | None, Field(description="New household name")] = None,
        locale: Annotated[str | None, Field(description="BCP-47 locale, e.g. 'es-ES'")] = None,
        timezone: Annotated[
            str | None, Field(description="IANA timezone, e.g. 'Europe/Madrid'")
        ] = None,
        expected_version: Annotated[
            int | None,
            Field(description="Household version for optimistic locking; omit to skip the check"),
        ] = None,
    ) -> dict[str, Any]:
        def run(session, membership, principal):
            household = household_service.get_household(session, principal.household_id)
            user = session.get(AppUser, principal.user_id)
            updated = household_service.update_household(
                session,
                household=household,
                user=user,
                payload=HouseholdUpdate(name=name, locale=locale, timezone=timezone),
                expected_version=expected_version,
                request_id="mcp",
            )
            return {
                "id": str(updated.id),
                "name": updated.name,
                "locale": updated.locale,
                "timezone": updated.timezone,
                "version": updated.version,
            }

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_list_activity",
        annotations=READ_ONLY.model_copy(update={"title": "Household activity feed"}),
        description=(
            "Recent domain events for the household (plans, purchases, completions, "
            "preparation). Useful to audit what the agent or humans changed."
        ),
    )
    def list_activity(
        ctx: Context,
        page: Annotated[int, Field(ge=1, description="Page number")] = 1,
        page_size: Annotated[int, Field(ge=1, le=50, description="Items per page")] = 20,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            rows, has_more, _counts = event_service.list_activity(
                session, membership, page=page, page_size=page_size
            )
            return {
                "page": page,
                "has_more": has_more,
                "events": [
                    {
                        "id": str(row.id),
                        "kind": row.kind,
                        "occurred_at": row.occurred_at,
                        "actor_user_id": row.actor_user_id,
                        "aggregate_type": row.aggregate_type,
                        "aggregate_id": row.aggregate_id,
                        "payload": row.payload,
                    }
                    for row in rows
                ],
            }

        return rt.call(ctx, run)
