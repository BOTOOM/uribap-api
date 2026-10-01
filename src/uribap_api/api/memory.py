from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.inventory_schemas import ProblemDetails
from uribap_api.api.memory_schemas import (
    DinerCreate,
    DinerPage,
    DinerResponse,
    DinerUpdate,
    HouseholdMemoryProfile,
    MemoryCreate,
    MemoryPage,
    MemoryResponse,
    MemoryUpdate,
)
from uribap_api.application import memory_service
from uribap_api.infrastructure.persistence.household_models import HouseholdMember

router = APIRouter(tags=["household-memory"])
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


@router.get("/diners", response_model=DinerPage, responses=ERROR_RESPONSES)
def list_diners_route(
    include_archived: bool = Query(default=False),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> DinerPage:
    return DinerPage(
        items=[
            DinerResponse.model_validate(diner)
            for diner in memory_service.list_diners(
                session, membership, include_archived=include_archived
            )
        ]
    )


@router.post(
    "/diners",
    response_model=DinerResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def create_diner_route(
    payload: DinerCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> DinerResponse:
    result = memory_service.create_diner(session, membership, payload, idempotency_key)
    return DinerResponse.model_validate(result.payload)


@router.patch("/diners/{diner_id}", response_model=DinerResponse, responses=ERROR_RESPONSES)
def update_diner_route(
    diner_id: UUID,
    payload: DinerUpdate,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> DinerResponse:
    diner = memory_service.update_diner(session, membership, diner_id, payload)
    return DinerResponse.model_validate(diner)


@router.delete(
    "/diners/{diner_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERROR_RESPONSES,
)
def archive_diner_route(
    diner_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> Response:
    memory_service.archive_diner(session, membership, diner_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/memories", response_model=MemoryPage, responses=ERROR_RESPONSES)
def list_memories_route(
    diner_id: UUID | None = Query(default=None),
    scope: Literal["all", "household", "diner"] = Query(default="all"),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=200),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MemoryPage:
    return MemoryPage(
        items=[
            MemoryResponse.model_validate(memory)
            for memory in memory_service.list_memories(
                session,
                membership,
                diner_id=diner_id,
                scope=scope,
                include_archived=include_archived,
                limit=limit,
            )
        ]
    )


@router.post(
    "/memories",
    response_model=MemoryResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def create_memory_route(
    payload: MemoryCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MemoryResponse:
    result = memory_service.create_memory(session, membership, payload, idempotency_key)
    return MemoryResponse.model_validate(result.payload)


@router.patch("/memories/{memory_id}", response_model=MemoryResponse, responses=ERROR_RESPONSES)
def update_memory_route(
    memory_id: UUID,
    payload: MemoryUpdate,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MemoryResponse:
    memory = memory_service.update_memory(session, membership, memory_id, payload)
    return MemoryResponse.model_validate(memory)


@router.delete(
    "/memories/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=ERROR_RESPONSES,
)
def archive_memory_route(
    memory_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> Response:
    memory_service.archive_memory(session, membership, memory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/memory/profile",
    response_model=HouseholdMemoryProfile,
    responses=ERROR_RESPONSES,
)
def memory_profile_route(
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> HouseholdMemoryProfile:
    return memory_service.get_memory_profile(session, membership)
