from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.inventory_schemas import ProblemDetails
from uribap_api.api.preparation_schemas import (
    PreparationTaskCreate,
    PreparationTaskMutation,
    PreparationTaskPage,
    PreparationTaskResponse,
)
from uribap_api.application.preparation_service import (
    create_manual_task,
    list_tasks,
    transition_task,
)
from uribap_api.domain.preparation.policies import (
    PreparationTaskAction,
    PreparationTaskStatus,
)
from uribap_api.infrastructure.persistence.household_models import HouseholdMember

router = APIRouter(prefix="/preparation-tasks", tags=["preparation-tasks"])
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


@router.get("", response_model=PreparationTaskPage, responses=ERROR_RESPONSES)
def list_tasks_route(
    status_filter: PreparationTaskStatus | None = Query(default=None, alias="status"),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> PreparationTaskPage:
    return PreparationTaskPage(items=list_tasks(session, membership, status_filter, from_dt, to_dt))


@router.post(
    "",
    response_model=PreparationTaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def create_task_route(
    payload: PreparationTaskCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> PreparationTaskResponse:
    result = create_manual_task(session, membership, payload, idempotency_key)
    return PreparationTaskResponse.model_validate(result.payload)


def _transition_route(
    action: PreparationTaskAction,
    task_id: UUID,
    payload: PreparationTaskMutation,
    idempotency_key: str | None,
    membership: HouseholdMember,
    session: Session,
) -> PreparationTaskResponse:
    result = transition_task(
        session,
        membership,
        task_id,
        action,
        payload.expected_version,
        idempotency_key,
    )
    return PreparationTaskResponse.model_validate(result.payload)


@router.post(
    "/{task_id}/complete",
    response_model=PreparationTaskResponse,
    responses=ERROR_RESPONSES,
)
def complete_task_route(
    task_id: UUID,
    payload: PreparationTaskMutation,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> PreparationTaskResponse:
    return _transition_route(
        PreparationTaskAction.COMPLETE, task_id, payload, idempotency_key, membership, session
    )


@router.post(
    "/{task_id}/cancel",
    response_model=PreparationTaskResponse,
    responses=ERROR_RESPONSES,
)
def cancel_task_route(
    task_id: UUID,
    payload: PreparationTaskMutation,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> PreparationTaskResponse:
    return _transition_route(
        PreparationTaskAction.CANCEL, task_id, payload, idempotency_key, membership, session
    )
