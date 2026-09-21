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
    MealPlanEntryResponse,
    MealPlanEntryUpdate,
    MealPlanEventPage,
    MealPlanResponse,
    MealPlanStateEventResponse,
    MealPlanTransition,
)
from uribap_api.application.planning_service import (
    add_entry,
    create_plan,
    delete_entry,
    get_current_plan,
    get_plan,
    list_entries,
    list_events,
    transition_plan,
    update_entry,
)
from uribap_api.domain.planning.policies import MealPlanAction
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.planning_models import (
    MealPlan,
    MealPlanEntry,
    MealPlanStateEvent,
)

router = APIRouter(prefix="/plans", tags=["plans"])
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


def entry_response(entry: MealPlanEntry) -> MealPlanEntryResponse:
    return MealPlanEntryResponse(
        id=entry.id,
        meal_plan_id=entry.meal_plan_id,
        planned_date=entry.planned_date,
        meal_type=entry.meal_type,
        recipe_version_id=entry.recipe_version_id,
        servings=entry.servings,
        position=entry.position,
        notes=entry.notes,
        added_by_user_id=entry.added_by_user_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def plan_response(
    session: Session, membership: HouseholdMember, plan: MealPlan
) -> MealPlanResponse:
    entries = list_entries(session, membership, plan.id)
    return MealPlanResponse(
        id=plan.id,
        household_id=plan.household_id,
        week_start_date=plan.week_start_date,
        state=plan.state,
        version=plan.version,
        entries=[entry_response(entry) for entry in entries],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def event_response(event: MealPlanStateEvent) -> MealPlanStateEventResponse:
    return MealPlanStateEventResponse(
        id=event.id,
        meal_plan_id=event.meal_plan_id,
        from_state=event.from_state,
        to_state=event.to_state,
        actor_user_id=event.actor_user_id,
        note=event.note,
        created_at=event.created_at,
    )


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
    plan = create_plan(session, membership, payload, idempotency_key)
    return plan_response(session, membership, plan)


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
    plan, _entry = add_entry(session, membership, plan_id, payload, idempotency_key)
    return plan_response(session, membership, plan)


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
    plan, _entry = update_entry(session, membership, plan_id, entry_id, payload, idempotency_key)
    return plan_response(session, membership, plan)


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
    plan = delete_entry(session, membership, plan_id, entry_id, expected_version, idempotency_key)
    return plan_response(session, membership, plan)


def _transition_route(
    action: MealPlanAction,
    plan_id: UUID,
    payload: MealPlanTransition,
    idempotency_key: str | None,
    membership: HouseholdMember,
    session: Session,
) -> MealPlanResponse:
    plan = transition_plan(session, membership, plan_id, action, payload, idempotency_key)
    return plan_response(session, membership, plan)


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
