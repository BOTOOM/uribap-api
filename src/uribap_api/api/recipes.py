from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.recipe_schemas import (
    RecipeCreate,
    RecipePage,
    RecipePublishResponse,
    RecipeResponse,
    RecipeVersionCreate,
)
from uribap_api.application.recipe_service import (
    create_recipe,
    create_version,
    favorite_recipe,
    get_recipe,
    list_recipes,
    publish_version,
    unfavorite_recipe,
)
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.recipe_models import Recipe, RecipeVersion

router = APIRouter(prefix="/recipes", tags=["recipes"])


def recipe_response(recipe: Recipe, version: RecipeVersion | None) -> RecipeResponse:
    return RecipeResponse(
        id=recipe.id,
        household_id=recipe.household_id,
        name=recipe.name,
        description=recipe.description,
        archived_at=recipe.archived_at,
        latest_version=version.version_number if version else None,
        latest_state=version.state if version else None,
    )


@router.get("", response_model=RecipePage)
def list_route(
    query: str | None = None,
    archived: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> RecipePage:
    items = list_recipes(session, membership, query, archived, limit)
    return RecipePage(
        items=[recipe_response(recipe, version) for recipe, version in items],
        page_info={"limit": min(limit, 100)},
    )


@router.post("", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def create_route(
    payload: RecipeCreate,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> RecipeResponse:
    recipe = create_recipe(session, membership, payload)
    version = session.scalar(
        select(RecipeVersion)
        .where(RecipeVersion.recipe_id == recipe.id)
        .order_by(desc(RecipeVersion.version_number))
    )
    return recipe_response(recipe, version)


@router.get("/{recipe_id}", response_model=RecipeResponse)
def get_route(
    recipe_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> RecipeResponse:
    recipe = get_recipe(session, membership, recipe_id)
    version = session.scalar(
        select(RecipeVersion)
        .where(RecipeVersion.recipe_id == recipe.id)
        .order_by(desc(RecipeVersion.version_number))
    )
    return recipe_response(recipe, version)


@router.post(
    "/{recipe_id}/versions", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED
)
def create_version_route(
    recipe_id: UUID,
    payload: RecipeVersionCreate,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> RecipeResponse:
    version = create_version(session, membership, recipe_id, payload)
    recipe = get_recipe(session, membership, recipe_id)
    return recipe_response(recipe, version)


@router.post("/{recipe_id}/versions/{version_number}/publish", response_model=RecipePublishResponse)
def publish_route(
    recipe_id: UUID,
    version_number: int,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> RecipePublishResponse:
    version = publish_version(session, membership, recipe_id, version_number)
    return RecipePublishResponse(
        recipe_id=recipe_id, version=version.version_number, state=version.state
    )


@router.post("/{recipe_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def favorite_route(
    recipe_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> None:
    favorite_recipe(session, membership, recipe_id)


@router.delete("/{recipe_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
def unfavorite_route(
    recipe_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> None:
    unfavorite_recipe(session, membership, recipe_id)
