from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID, uuid4

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from uribap_api.api.memory_schemas import (
    DinerCreate,
    DinerResponse,
    DinerUpdate,
    MemoryCreate,
    MemoryResponse,
    MemoryUpdate,
)
from uribap_api.application import memory_service
from uribap_api.domain.household.memory import MemoryKind
from uribap_api.mcp.runtime import McpRuntime

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)


def _uuid(value: str, field_name: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ToolError(f"{field_name} must be a UUID.") from exc


def register(mcp: FastMCP, rt: McpRuntime) -> None:
    @mcp.tool(
        name="uribap_get_memory",
        annotations=READ_ONLY.model_copy(update={"title": "Household food memory"}),
        description=(
            "Read what the household remembers: each diner's likes, dislikes, restrictions and "
            "goals plus household-wide notes. Read this before suggesting or planning meals and "
            "respect restrictions."
        ),
    )
    def get_memory(ctx: Context) -> dict[str, Any]:
        def run(session, membership, _principal):
            return memory_service.get_memory_profile(session, membership).model_dump(mode="json")

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_add_diner",
        annotations=WRITE.model_copy(update={"title": "Add household diner"}),
        description="Create an account-linked or account-less diner profile.",
    )
    def add_diner(
        ctx: Context,
        display_name: Annotated[str, Field(min_length=1, max_length=80)],
        member_user_id: str | None = None,
        idempotency_key: Annotated[str | None, Field(max_length=128)] = None,
    ) -> dict[str, Any]:
        def run(session, membership, _principal):
            result = memory_service.create_diner(
                session,
                membership,
                DinerCreate(
                    display_name=display_name,
                    member_user_id=(
                        _uuid(member_user_id, "member_user_id")
                        if member_user_id is not None
                        else None
                    ),
                ),
                idempotency_key if idempotency_key is not None else str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_update_diner",
        annotations=WRITE.model_copy(update={"title": "Update household diner"}),
        description=(
            "Update a diner name or link it to a household member. "
            "Set unlink_member=true to explicitly remove a member link."
        ),
    )
    def update_diner(
        ctx: Context,
        diner_id: Annotated[str, Field(description="Diner UUID")],
        display_name: Annotated[str | None, Field(min_length=1, max_length=80)] = None,
        member_user_id: str | None = None,
        unlink_member: bool = False,
        expected_version: Annotated[int | None, Field(ge=1)] = None,
    ) -> dict[str, Any]:
        def run(session, membership, _principal):
            if unlink_member and member_user_id is not None:
                raise ToolError("Pass unlink_member or member_user_id, not both.")
            diner = memory_service.get_diner(session, membership, _uuid(diner_id, "diner_id"))
            changes: dict[str, Any] = {
                "expected_version": (
                    expected_version if expected_version is not None else diner.version
                )
            }
            if display_name is not None:
                changes["display_name"] = display_name
            if unlink_member:
                changes["member_user_id"] = None
            elif member_user_id is not None:
                changes["member_user_id"] = _uuid(member_user_id, "member_user_id")
            updated = memory_service.update_diner(
                session,
                membership,
                diner.id,
                DinerUpdate(**changes),
            )
            return DinerResponse.model_validate(updated).model_dump(mode="json")

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_archive_diner",
        annotations=DESTRUCTIVE.model_copy(update={"title": "Archive household diner"}),
        description="Archive a diner profile; its memories remain stored but are not active.",
    )
    def archive_diner(
        ctx: Context,
        diner_id: Annotated[str, Field(description="Diner UUID")],
    ) -> dict[str, Any]:
        def run(session, membership, _principal):
            parsed_id = _uuid(diner_id, "diner_id")
            memory_service.archive_diner(session, membership, parsed_id)
            return {"diner_id": str(parsed_id), "archived": True}

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_remember",
        annotations=WRITE.model_copy(update={"title": "Remember household preference"}),
        description=(
            "Save a durable memory for a diner or the whole household (likes, dislikes, "
            "allergies/restrictions, goals, notes). Use when the user states a lasting preference; "
            "never for one-off plans."
        ),
    )
    def remember(
        ctx: Context,
        content: Annotated[str, Field(min_length=1, max_length=1000)],
        kind: MemoryKind = MemoryKind.NOTE,
        diner_id: str | None = None,
        diner_name: str | None = None,
        idempotency_key: Annotated[str | None, Field(max_length=128)] = None,
    ) -> dict[str, Any]:
        def run(session, membership, _principal):
            if diner_id is not None and diner_name is not None:
                raise ToolError("Pass diner_id or diner_name, not both.")
            requested_payload = MemoryCreate(kind=kind, content=content)
            if diner_name is not None and idempotency_key is not None:
                replay = memory_service.replay_memory_create_by_name(
                    session,
                    membership,
                    requested_payload,
                    diner_name,
                    idempotency_key,
                )
                if replay is not None:
                    return replay.payload
            resolved_diner_id = None
            if diner_id is not None:
                resolved_diner_id = _uuid(diner_id, "diner_id")
            elif diner_name is not None:
                diner = memory_service.find_active_diner_by_name(session, membership, diner_name)
                if diner is None:
                    raise ToolError(
                        f"No active diner named '{diner_name}'. "
                        "Create the diner first with uribap_add_diner."
                    )
                resolved_diner_id = diner.id
            result = memory_service.create_memory(
                session,
                membership,
                MemoryCreate(
                    kind=kind,
                    content=content,
                    diner_id=resolved_diner_id,
                ),
                idempotency_key if idempotency_key is not None else str(uuid4()),
                requested_diner_name=diner_name,
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_update_memory",
        annotations=WRITE.model_copy(update={"title": "Update household memory"}),
        description="Update a memory's content or kind.",
    )
    def update_memory(
        ctx: Context,
        memory_id: Annotated[str, Field(description="Memory UUID")],
        content: Annotated[str | None, Field(min_length=1, max_length=1000)] = None,
        kind: MemoryKind | None = None,
        expected_version: Annotated[int | None, Field(ge=1)] = None,
    ) -> dict[str, Any]:
        def run(session, membership, _principal):
            parsed_id = _uuid(memory_id, "memory_id")
            memory = memory_service.get_memory(session, membership, parsed_id)
            changes: dict[str, Any] = {
                "expected_version": (
                    expected_version if expected_version is not None else memory.version
                )
            }
            if content is not None:
                changes["content"] = content
            if kind is not None:
                changes["kind"] = kind
            updated = memory_service.update_memory(
                session,
                membership,
                parsed_id,
                MemoryUpdate(**changes),
            )
            return MemoryResponse.model_validate(updated).model_dump(mode="json")

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_forget_memory",
        annotations=DESTRUCTIVE.model_copy(update={"title": "Forget household memory"}),
        description="Archive a household or diner memory.",
    )
    def forget_memory(
        ctx: Context,
        memory_id: Annotated[str, Field(description="Memory UUID")],
    ) -> dict[str, Any]:
        def run(session, membership, _principal):
            parsed_id = _uuid(memory_id, "memory_id")
            memory_service.archive_memory(session, membership, parsed_id)
            return {"memory_id": str(parsed_id), "archived": True}

        return rt.call(ctx, run)
