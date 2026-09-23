from __future__ import annotations

from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.orm import Session
from starlette.applications import Starlette

from uribap_api.mcp import (
    tools_catalog,
    tools_household,
    tools_inventory,
    tools_plan,
    tools_shopping,
)
from uribap_api.mcp.auth import McpAuthMiddleware
from uribap_api.mcp.runtime import McpRuntime

INSTRUCTIONS = """Uribap household food management.

You act on behalf of ONE household member inside ONE household (fixed by the
bearer token). Start with uribap_get_context to learn names and ids.

Typical flows:
- Plan the week: uribap_get_plan → uribap_list_recipes/uribap_create_recipe →
  uribap_add_plan_entry → uribap_transition_plan(propose, approve).
- Shop: uribap_get_forecast or uribap_create_shopping_list →
  uribap_purchase_shopping_item (creates the lot) or uribap_register_purchase.
- Cook: uribap_complete_meal deducts real stock; uribap_reopen_completion undoes it.
- Pantry: uribap_get_inventory (real lots), uribap_get_forecast (projected need).

All writes are idempotent (a key is generated per call; pass your own
`idempotency_key` to deduplicate retries). Optimistic concurrency is handled
automatically — on a 409/conflict error, re-read the entity and retry the call.
"""


def build_mcp_server(
    session_factory: Callable[[], Session], http_path: str
) -> FastMCP:
    mcp = FastMCP(
        "uribap",
        instructions=INSTRUCTIONS,
        stateless_http=True,
        json_response=True,
        streamable_http_path=http_path,
        # Bearer-token auth already guards the endpoint; Host-header DNS
        # rebinding checks would 421 every remote (Coolify) request.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
    runtime = McpRuntime(session_factory)
    for module in (
        tools_household,
        tools_catalog,
        tools_inventory,
        tools_plan,
        tools_shopping,
    ):
        module.register(mcp, runtime)
    return mcp


def build_mcp_app(
    mcp_server: FastMCP, session_factory: Callable[[], Session]
) -> Starlette:
    """The ASGI app to mount: MCP transport behind bearer-token auth."""
    app = mcp_server.streamable_http_app()
    app.add_middleware(McpAuthMiddleware, session_factory=session_factory)
    return app
