from __future__ import annotations

import json
from collections.abc import Callable

from sqlalchemy.orm import Session
from starlette.types import ASGIApp, Receive, Scope, Send

from uribap_api.mcp.tokens import TOKEN_PREFIX, resolve_token

PRINCIPAL_SCOPE_KEY = "uribap.mcp.principal"


class McpAuthMiddleware:
    """Pure-ASGI bearer auth for the mounted MCP app.

    Resolves `Authorization: Bearer uribap_mcp_*` into an `McpPrincipal`
    stored in `scope["state"]` and `scope[PRINCIPAL_SCOPE_KEY]`.
    """

    def __init__(self, app: ASGIApp, session_factory: Callable[[], Session]) -> None:
        self.app = app
        self._session_factory = session_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        scheme, _, credential = authorization.partition(" ")
        if scheme.lower() != "bearer" or not credential.startswith(TOKEN_PREFIX):
            await self._reject(send, "Missing or invalid MCP bearer token.")
            return

        session = self._session_factory()
        try:
            principal = resolve_token(session, credential)
        finally:
            session.close()
        if principal is None:
            await self._reject(send, "The MCP token is revoked or unknown.")
            return

        scope.setdefault("state", {})[PRINCIPAL_SCOPE_KEY] = principal
        scope[PRINCIPAL_SCOPE_KEY] = principal
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(send: Send, detail: str) -> None:
        body = json.dumps({"error": "unauthorized", "detail": detail}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"www-authenticate", b'Bearer realm="uribap-mcp"'),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
