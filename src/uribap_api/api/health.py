from typing import Literal

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from uribap_api.application.health_service import database_is_ready
from uribap_api.infrastructure.logging import get_request_id

router = APIRouter(prefix="/health", tags=["health"])


class LiveHealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class DependencyHealth(BaseModel):
    status: Literal["ok", "unavailable"]


class ReadyHealthResponse(BaseModel):
    status: Literal["ok", "unavailable"]
    service: str
    version: str
    dependencies: dict[str, DependencyHealth]
    request_id: str | None = Field(default=None, serialization_alias="requestId")


@router.get("/live", response_model=LiveHealthResponse)
def live(request: Request) -> LiveHealthResponse:
    settings = request.app.state.settings
    return LiveHealthResponse(status="ok", service=settings.app_name, version=settings.app_version)


@router.get("/ready", response_model=ReadyHealthResponse)
def ready(request: Request) -> ReadyHealthResponse | JSONResponse:
    settings = request.app.state.settings
    try:
        database_is_ready(request.app.state.engine)
    except Exception:
        payload = ReadyHealthResponse(
            status="unavailable",
            service=settings.app_name,
            version=settings.app_version,
            dependencies={"database": DependencyHealth(status="unavailable")},
            request_id=get_request_id() or None,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload.model_dump(by_alias=True),
        )

    return ReadyHealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        dependencies={"database": DependencyHealth(status="ok")},
        request_id=get_request_id() or None,
    )
