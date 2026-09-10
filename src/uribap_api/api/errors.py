from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.logging import get_request_id


def problem_response(
    *,
    status_code: int,
    title: str,
    detail: str,
    code: str,
    request: Request,
    error_type: str = "about:blank",
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": error_type,
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": request.url.path,
            "code": code,
            "requestId": get_request_id(),
        },
        media_type="application/problem+json",
    )


async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    del exc
    return problem_response(
        status_code=422,
        title="Request validation failed",
        detail="The request contains invalid fields.",
        code="validation_error",
        request=request,
        error_type="https://api.uribap.app/problems/validation-error",
    )


async def http_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        return problem_response(
            status_code=500,
            title="Internal server error",
            detail="The service could not complete the request.",
            code="internal_error",
            request=request,
        )
    detail = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return problem_response(
        status_code=exc.status_code,
        title="Request failed",
        detail=detail,
        code=f"http_{exc.status_code}",
        request=request,
    )


async def domain_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        return problem_response(
            status_code=500,
            title="Internal server error",
            detail="The service could not complete the request.",
            code="internal_error",
            request=request,
        )
    return problem_response(
        status_code=exc.status_code,
        title=exc.title,
        detail=exc.detail,
        code=exc.code,
        request=request,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    del exc
    return problem_response(
        status_code=500,
        title="Internal server error",
        detail="The service could not complete the request.",
        code="internal_error",
        request=request,
    )
