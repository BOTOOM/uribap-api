from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError
from sqlalchemy.orm import Session

from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.mcp.auth import PRINCIPAL_SCOPE_KEY
from uribap_api.mcp.serialization import to_jsonable
from uribap_api.mcp.tokens import McpPrincipal, load_membership

if TYPE_CHECKING:
    from starlette.requests import Request

T = TypeVar("T")


class McpRuntime:
    """Shared plumbing for every tool: principal + session lifecycle + errors."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def _request(self, ctx: Context) -> Request:
        request_context = ctx.request_context
        request = getattr(request_context, "request", None) if request_context else None
        if request is None:
            raise ToolError("HTTP request context unavailable for this MCP call.")
        return request

    def principal(self, ctx: Context) -> McpPrincipal:
        request = self._request(ctx)
        principal = request.scope.get(PRINCIPAL_SCOPE_KEY)
        if principal is None:
            state = request.scope.get("state") or {}
            principal = state.get(PRINCIPAL_SCOPE_KEY)
        if principal is None:
            raise ToolError("MCP principal missing — the token did not resolve.")
        return principal

    def call(
        self,
        ctx: Context,
        fn: Callable[[Session, HouseholdMember, McpPrincipal], Any],
    ) -> dict[str, Any]:
        """Run `fn(session, membership, principal)`; return a JSON-safe dict.

        Returning the object (not a JSON string) lets FastMCP expose it as
        `structuredContent` so clients can consume typed data directly.
        """
        principal = self.principal(ctx)
        session = self._session_factory()
        try:
            membership = load_membership(session, principal)
            return to_jsonable(fn(session, membership, principal))
        except DomainError as exc:
            raise ToolError(
                f"{exc.title} [{exc.code}]: {exc.detail}"
            ) from exc
        finally:
            session.close()
