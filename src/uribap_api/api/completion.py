from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from uribap_api.api.completion_schemas import (
    MealCompletionCorrect,
    MealCompletionCreate,
    MealCompletionPage,
    MealCompletionReopen,
    MealCompletionResponse,
)
from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.inventory_schemas import ProblemDetails
from uribap_api.application.completion_service import (
    complete_entry,
    correct_line,
    get_completion,
    list_completions,
    reopen_completion,
)
from uribap_api.domain.completion.policies import MealCompletionState
from uribap_api.infrastructure.persistence.household_models import HouseholdMember

plans_router = APIRouter(prefix="/plans", tags=["meal-completions"])
router = APIRouter(prefix="/meal-completions", tags=["meal-completions"])
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


@plans_router.post(
    "/{plan_id}/entries/{entry_id}/complete",
    response_model=MealCompletionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def complete_entry_route(
    plan_id: UUID,
    entry_id: UUID,
    payload: MealCompletionCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealCompletionResponse:
    result = complete_entry(session, membership, plan_id, entry_id, payload, idempotency_key)
    return MealCompletionResponse.model_validate(result.payload)


@router.get("", response_model=MealCompletionPage, responses=ERROR_RESPONSES)
def list_completions_route(
    entry_id: UUID | None = Query(default=None),
    state: MealCompletionState | None = Query(default=None),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealCompletionPage:
    return MealCompletionPage(
        items=list_completions(session, membership, entry_id, state, from_dt, to_dt)
    )


@router.get(
    "/{completion_id}", response_model=MealCompletionResponse, responses=ERROR_RESPONSES
)
def get_completion_route(
    completion_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealCompletionResponse:
    return get_completion(session, membership, completion_id)


@router.post(
    "/{completion_id}/lines/{line_id}/correct",
    response_model=MealCompletionResponse,
    responses=ERROR_RESPONSES,
)
def correct_line_route(
    completion_id: UUID,
    line_id: UUID,
    payload: MealCompletionCorrect,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealCompletionResponse:
    result = correct_line(
        session,
        membership,
        completion_id,
        line_id,
        payload.expected_version,
        payload.actual_amount,
        payload.unit,
        idempotency_key,
    )
    return MealCompletionResponse.model_validate(result.payload)


@router.post(
    "/{completion_id}/reopen",
    response_model=MealCompletionResponse,
    responses=ERROR_RESPONSES,
)
def reopen_completion_route(
    completion_id: UUID,
    payload: MealCompletionReopen,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealCompletionResponse:
    result = reopen_completion(
        session,
        membership,
        completion_id,
        payload.expected_version,
        payload.reason,
        idempotency_key,
    )
    return MealCompletionResponse.model_validate(result.payload)
