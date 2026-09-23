from collections.abc import Callable
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from uribap_api.api.errors import (
    domain_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from uribap_api.api.router import api_router
from uribap_api.config import get_settings
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.database import create_database_engine, create_session_factory
from uribap_api.infrastructure.identity.jwt_validator import TokenValidator
from uribap_api.infrastructure.logging import RequestIdMiddleware, configure_logging
from uribap_api.infrastructure.security_headers import SecurityHeadersMiddleware
from uribap_api.mcp.server import build_mcp_app, build_mcp_server

settings = get_settings()


class _SessionFactoryRef:
    """Late-bound session factory: the FastAPI lifespan fills it at startup."""

    factory: Callable[[], Session] | None = None

    def __call__(self) -> Session:
        if self.factory is None:
            raise RuntimeError("The database session factory is not ready yet.")
        return self.factory()


MCP_PATH = f"{settings.api_prefix}/mcp"

_sessions = _SessionFactoryRef()


class _McpDispatch:
    """ASGI app forwarding to the per-lifespan MCP app built in `lifespan`.

    The StreamableHTTP session manager is single-use, so a fresh FastMCP
    instance is created on every app startup (each TestClient gets its own).
    A class instance is used because Starlette treats function endpoints as
    request-response handlers rather than raw ASGI apps.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await scope["app"].state.mcp_asgi(scope, receive, send)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.log_level)
    engine = create_database_engine(settings)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.token_validator = TokenValidator(settings)
    _sessions.factory = app.state.session_factory
    app.state.mcp_server = build_mcp_server(_sessions, MCP_PATH)
    app.state.mcp_asgi = build_mcp_app(app.state.mcp_server, _sessions)
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(app.state.mcp_server.session_manager.run())
        yield
    engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Uribap household food planning API",
    root_path="",
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(DomainError, domain_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.include_router(api_router, prefix=settings.api_prefix)
# The MCP transport is registered as a plain Route (not a Mount) so POSTs to
# /api/v1/mcp hit it directly — Mount would 307-redirect to /mcp/, which breaks
# JSON-RPC clients. The dispatch forwards to the app built in `lifespan`.
app.router.routes.append(
    Route(MCP_PATH, endpoint=_McpDispatch(), methods=["GET", "POST", "DELETE"], name="mcp")
)
