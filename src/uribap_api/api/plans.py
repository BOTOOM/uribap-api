from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.inventory_schemas import ProblemDetails
from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanEntryUpdate,
    MealPlanEventPage,
    MealPlanResponse,
    MealPlanTransition,
)
from uribap_api.application.planning_service import (
    add_entry,
    create_plan,
    delete_entry,
    event_response,
    get_current_plan,
    get_plan,
    list_events,
    plan_response,
    transition_plan,
    update_entry,
)
from uribap_api.domain.planning.policies import MealPlanAction
from uribap_api.infrastructure.persistence.household_models import HouseholdMember

router = APIRouter(prefix="/plans", tags=["plans"])
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


@router.post(
    "",
    response_model=MealPlanResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def create_plan_route(
    payload: MealPlanCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    result = create_plan(session, membership, payload, idempotency_key)
    return MealPlanResponse.model_validate(result.payload)


@router.get("/current", response_model=MealPlanResponse, responses=ERROR_RESPONSES)
def current_plan_route(
    week_start: date = Query(),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    return plan_response(session, membership, get_current_plan(session, membership, week_start))


@router.get("/{plan_id}", response_model=MealPlanResponse, responses=ERROR_RESPONSES)
def get_plan_route(
    plan_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    return plan_response(session, membership, get_plan(session, membership, plan_id))


@router.post(
    "/{plan_id}/entries",
    response_model=MealPlanResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def add_entry_route(
    plan_id: UUID,
    payload: MealPlanEntryCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    result = add_entry(session, membership, plan_id, payload, idempotency_key)
    return MealPlanResponse.model_validate(result.payload)


@router.patch(
    "/{plan_id}/entries/{entry_id}", response_model=MealPlanResponse, responses=ERROR_RESPONSES
)
def update_entry_route(
    plan_id: UUID,
    entry_id: UUID,
    payload: MealPlanEntryUpdate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    result = update_entry(session, membership, plan_id, entry_id, payload, idempotency_key)
    return MealPlanResponse.model_validate(result.payload)


@router.delete(
    "/{plan_id}/entries/{entry_id}", response_model=MealPlanResponse, responses=ERROR_RESPONSES
)
def delete_entry_route(
    plan_id: UUID,
    entry_id: UUID,
    expected_version: int = Query(ge=1),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    result = delete_entry(session, membership, plan_id, entry_id, expected_version, idempotency_key)
    return MealPlanResponse.model_validate(result.payload)


def _transition_route(
    action: MealPlanAction,
    plan_id: UUID,
    payload: MealPlanTransition,
    idempotency_key: str | None,
    membership: HouseholdMember,
    session: Session,
) -> MealPlanResponse:
    result = transition_plan(session, membership, plan_id, action, payload, idempotency_key)
    return MealPlanResponse.model_validate(result.payload)


@router.post("/{plan_id}/propose", response_model=MealPlanResponse, responses=ERROR_RESPONSES)
def propose_route(
    plan_id: UUID,
    payload: MealPlanTransition,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    return _transition_route(
        MealPlanAction.PROPOSE, plan_id, payload, idempotency_key, membership, session
    )


@router.post("/{plan_id}/approve", response_model=MealPlanResponse, responses=ERROR_RESPONSES)
def approve_route(
    plan_id: UUID,
    payload: MealPlanTransition,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    return _transition_route(
        MealPlanAction.APPROVE, plan_id, payload, idempotency_key, membership, session
    )


@router.post("/{plan_id}/reopen", response_model=MealPlanResponse, responses=ERROR_RESPONSES)
def reopen_route(
    plan_id: UUID,
    payload: MealPlanTransition,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    return _transition_route(
        MealPlanAction.REOPEN, plan_id, payload, idempotency_key, membership, session
    )


@router.post("/{plan_id}/archive", response_model=MealPlanResponse, responses=ERROR_RESPONSES)
def archive_route(
    plan_id: UUID,
    payload: MealPlanTransition,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanResponse:
    return _transition_route(
        MealPlanAction.ARCHIVE, plan_id, payload, idempotency_key, membership, session
    )


@router.get("/{plan_id}/events", response_model=MealPlanEventPage, responses=ERROR_RESPONSES)
def events_route(
    plan_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> MealPlanEventPage:
    return MealPlanEventPage(
        items=[event_response(item) for item in list_events(session, membership, plan_id)]
    )
