from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.inventory_schemas import ProblemDetails
from uribap_api.api.shopping_schemas import (
    ShoppingListCreate,
    ShoppingListResponse,
    ShoppingMutation,
    ShoppingPurchase,
)
from uribap_api.application.shopping_service import (
    create_shopping_list,
    get_current_list,
    get_shopping_list,
    list_items,
    list_response,
    purchase_item,
    transition_item,
    transition_list,
)
from uribap_api.domain.shopping.policies import ShoppingItemAction, ShoppingListAction
from uribap_api.infrastructure.persistence.household_models import HouseholdMember

router = APIRouter(prefix="/shopping-lists", tags=["shopping-lists"])
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


def _full_response(
    session: Session, membership: HouseholdMember, list_id: UUID
) -> ShoppingListResponse:
    shopping_list = get_shopping_list(session, membership, list_id)
    return list_response(
        session, membership, shopping_list, list_items(session, membership, list_id)
    )


@router.post(
    "",
    response_model=ShoppingListResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def create_list_route(
    payload: ShoppingListCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> ShoppingListResponse:
    result = create_shopping_list(session, membership, payload, idempotency_key)
    return ShoppingListResponse.model_validate(result.payload)


@router.get("/current", response_model=ShoppingListResponse, responses=ERROR_RESPONSES)
def current_list_route(
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> ShoppingListResponse:
    shopping_list = get_current_list(session, membership)
    return list_response(
        session, membership, shopping_list, list_items(session, membership, shopping_list.id)
    )


@router.get("/{list_id}", response_model=ShoppingListResponse, responses=ERROR_RESPONSES)
def get_list_route(
    list_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> ShoppingListResponse:
    return _full_response(session, membership, list_id)


@router.post(
    "/{list_id}/items/{item_id}/purchase",
    response_model=ShoppingListResponse,
    responses=ERROR_RESPONSES,
)
def purchase_item_route(
    list_id: UUID,
    item_id: UUID,
    payload: ShoppingPurchase,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> ShoppingListResponse:
    result = purchase_item(session, membership, list_id, item_id, payload, idempotency_key)
    return ShoppingListResponse.model_validate(result.payload)


def _item_transition_route(
    action: ShoppingItemAction,
    list_id: UUID,
    item_id: UUID,
    payload: ShoppingMutation,
    idempotency_key: str | None,
    membership: HouseholdMember,
    session: Session,
) -> ShoppingListResponse:
    result = transition_item(
        session,
        membership,
        list_id,
        item_id,
        action,
        payload.expected_version,
        idempotency_key,
    )
    return ShoppingListResponse.model_validate(result.payload)


@router.post(
    "/{list_id}/items/{item_id}/skip",
    response_model=ShoppingListResponse,
    responses=ERROR_RESPONSES,
)
def skip_item_route(
    list_id: UUID,
    item_id: UUID,
    payload: ShoppingMutation,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> ShoppingListResponse:
    return _item_transition_route(
        ShoppingItemAction.SKIP, list_id, item_id, payload, idempotency_key, membership, session
    )


@router.post(
    "/{list_id}/items/{item_id}/restore",
    response_model=ShoppingListResponse,
    responses=ERROR_RESPONSES,
)
def restore_item_route(
    list_id: UUID,
    item_id: UUID,
    payload: ShoppingMutation,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> ShoppingListResponse:
    return _item_transition_route(
        ShoppingItemAction.RESTORE, list_id, item_id, payload, idempotency_key, membership, session
    )


def _list_transition_route(
    action: ShoppingListAction,
    list_id: UUID,
    payload: ShoppingMutation,
    idempotency_key: str | None,
    membership: HouseholdMember,
    session: Session,
) -> ShoppingListResponse:
    result = transition_list(
        session, membership, list_id, action, payload.expected_version, idempotency_key
    )
    return ShoppingListResponse.model_validate(result.payload)


@router.post("/{list_id}/complete", response_model=ShoppingListResponse, responses=ERROR_RESPONSES)
def complete_list_route(
    list_id: UUID,
    payload: ShoppingMutation,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> ShoppingListResponse:
    return _list_transition_route(
        ShoppingListAction.COMPLETE, list_id, payload, idempotency_key, membership, session
    )


@router.post("/{list_id}/reopen", response_model=ShoppingListResponse, responses=ERROR_RESPONSES)
def reopen_list_route(
    list_id: UUID,
    payload: ShoppingMutation,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> ShoppingListResponse:
    return _list_transition_route(
        ShoppingListAction.REOPEN, list_id, payload, idempotency_key, membership, session
    )


@router.post("/{list_id}/archive", response_model=ShoppingListResponse, responses=ERROR_RESPONSES)
def archive_list_route(
    list_id: UUID,
    payload: ShoppingMutation,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> ShoppingListResponse:
    return _list_transition_route(
        ShoppingListAction.ARCHIVE, list_id, payload, idempotency_key, membership, session
    )
