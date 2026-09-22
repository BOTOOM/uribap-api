from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import (
    get_session,
    require_household_membership,
)
from uribap_api.api.inventory_schemas import ProblemDetails
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.mcp import tokens as mcp_tokens

router = APIRouter(prefix="/households/{household_id}/mcp-tokens", tags=["mcp-tokens"])

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


class McpTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return " ".join(value.split())


class McpTokenResponse(BaseModel):
    id: UUID
    name: str
    token_prefix: str
    last_used_at: datetime | None
    created_at: datetime


class McpTokenCreatedResponse(McpTokenResponse):
    token: str


class McpTokenPage(BaseModel):
    items: list[McpTokenResponse]


def _response(token) -> McpTokenResponse:
    return McpTokenResponse(
        id=token.id,
        name=token.name,
        token_prefix=token.token_prefix,
        last_used_at=token.last_used_at,
        created_at=token.created_at,
    )


@router.get("", response_model=McpTokenPage, responses=ERROR_RESPONSES)
def list_tokens(
    household_id: UUID,
    membership: HouseholdMember = Depends(require_household_membership()),
    session: Session = Depends(get_session),
) -> McpTokenPage:
    return McpTokenPage(
        items=[_response(token) for token in mcp_tokens.list_tokens(session, membership)]
    )


@router.post(
    "",
    response_model=McpTokenCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def create_token(
    household_id: UUID,
    payload: McpTokenCreate,
    membership: HouseholdMember = Depends(require_household_membership()),
    session: Session = Depends(get_session),
) -> McpTokenCreatedResponse:
    token, plaintext = mcp_tokens.create_token(session, membership, payload.name)
    return McpTokenCreatedResponse(**_response(token).model_dump(), token=plaintext)


@router.delete(
    "/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ERROR_RESPONSES,
)
def revoke_token(
    household_id: UUID,
    token_id: UUID,
    response: Response,
    membership: HouseholdMember = Depends(require_household_membership()),
    session: Session = Depends(get_session),
) -> None:
    if not mcp_tokens.revoke_token(session, membership, token_id):
        raise DomainError(
            "not_found", "Token not found", "The MCP token could not be found.", 404
        )
    response.status_code = status.HTTP_204_NO_CONTENT
