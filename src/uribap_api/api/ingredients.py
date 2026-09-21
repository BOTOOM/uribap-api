from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.recipe_schemas import (
    IngredientCreate,
    IngredientPage,
    IngredientResponse,
    IngredientUpdate,
)
from uribap_api.application.ingredient_service import (
    archive_ingredient,
    create_ingredient,
    get_ingredient,
    list_ingredients,
    update_ingredient,
)
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient

router = APIRouter(prefix="/ingredients", tags=["ingredients"])


def response(ingredient: Ingredient) -> IngredientResponse:
    return IngredientResponse(
        id=ingredient.id,
        household_id=ingredient.household_id,
        name=ingredient.name,
        normalized_name=ingredient.normalized_name,
        category=ingredient.category,
        dimension=ingredient.dimension,
        base_unit=ingredient.base_unit,
        archived_at=ingredient.archived_at,
    )


@router.get("", response_model=IngredientPage)
def list_route(
    query: str | None = None,
    dimension: str | None = None,
    include_global: bool = True,
    limit: int = Query(default=50, ge=1, le=100),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> IngredientPage:
    items = list_ingredients(session, membership, query, dimension, include_global, limit)
    return IngredientPage(
        items=[response(item) for item in items], page_info={"limit": min(limit, 100)}
    )


@router.post("", response_model=IngredientResponse, status_code=status.HTTP_201_CREATED)
def create_route(
    payload: IngredientCreate,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> IngredientResponse:
    return response(create_ingredient(session, membership, payload))


@router.get("/{ingredient_id}", response_model=IngredientResponse)
def get_route(
    ingredient_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> IngredientResponse:
    return response(get_ingredient(session, membership, ingredient_id))


@router.patch("/{ingredient_id}", response_model=IngredientResponse)
def update_route(
    ingredient_id: UUID,
    payload: IngredientUpdate,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> IngredientResponse:
    return response(update_ingredient(session, membership, ingredient_id, payload))


@router.post("/{ingredient_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_route(
    ingredient_id: UUID,
    response: Response,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> None:
    archive_ingredient(session, membership, ingredient_id)
    response.status_code = status.HTTP_204_NO_CONTENT
