from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership, get_session
from uribap_api.api.inventory_schemas import ProblemDetails
from uribap_api.api.preparation_schemas import PreparationRuleCreate, PreparationRuleResponse
from uribap_api.api.recipe_schemas import (
    PublishedRecipeVersionPage,
    PublishedRecipeVersionResponse,
    RecipeCreate,
    RecipePage,
    RecipePublishResponse,
    RecipeResponse,
    RecipeVersionCreate,
    RecipeVersionDetailResponse,
    RecipeVersionIngredientLine,
    RecipeVersionIngredientsPut,
)
from uribap_api.application.preparation_service import add_rule, delete_rule
from uribap_api.application.recipe_service import (
    create_recipe,
    create_version,
    favorite_recipe,
    get_recipe,
    get_version,
    list_published_versions,
    list_recipes,
    list_version_ingredients,
    publish_version,
    replace_version_ingredients,
    unfavorite_recipe,
)
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeVersion,
    RecipeVersionIngredient,
)

router = APIRouter(prefix="/recipes", tags=["recipes"])
ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ProblemDetails},
    403: {"model": ProblemDetails},
    404: {"model": ProblemDetails},
    409: {"model": ProblemDetails},
    422: {"model": ProblemDetails},
}


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


@router.get("/published-versions", response_model=PublishedRecipeVersionPage)
def published_versions_route(
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> PublishedRecipeVersionPage:
    return PublishedRecipeVersionPage(
        items=[
            PublishedRecipeVersionResponse(
                recipe_version_id=version.id,
                recipe_id=recipe.id,
                recipe_name=recipe.name,
                version_number=version.version_number,
                base_servings=version.base_servings,
                prep_minutes=version.prep_minutes,
            )
            for version, recipe in list_published_versions(session, membership)
        ]
    )


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


def version_detail_response(
    session: Session, version: RecipeVersion, lines: list[RecipeVersionIngredient]
) -> RecipeVersionDetailResponse:
    names = (
        {
            row.id: row.name
            for row in session.scalars(
                select(Ingredient).where(Ingredient.id.in_({line.ingredient_id for line in lines}))
            ).all()
        }
        if lines
        else {}
    )
    return RecipeVersionDetailResponse(
        recipe_id=version.recipe_id,
        version_number=version.version_number,
        state=version.state,
        base_servings=version.base_servings,
        prep_minutes=version.prep_minutes,
        ingredients=[
            RecipeVersionIngredientLine(
                id=line.id,
                ingredient_id=line.ingredient_id,
                ingredient_name=names.get(line.ingredient_id, ""),
                amount=Decimal(str(line.amount)),
                unit=line.unit,
                optional=line.optional,
            )
            for line in lines
        ],
    )


@router.get(
    "/{recipe_id}/versions/{version_number}",
    response_model=RecipeVersionDetailResponse,
    responses=ERROR_RESPONSES,
)
def get_version_route(
    recipe_id: UUID,
    version_number: int,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> RecipeVersionDetailResponse:
    version = get_version(session, membership, recipe_id, version_number)
    return version_detail_response(session, version, list_version_ingredients(session, version))


@router.put(
    "/{recipe_id}/versions/{version_number}/ingredients",
    response_model=RecipeVersionDetailResponse,
    responses=ERROR_RESPONSES,
)
def put_version_ingredients_route(
    recipe_id: UUID,
    version_number: int,
    payload: RecipeVersionIngredientsPut,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> RecipeVersionDetailResponse:
    lines = replace_version_ingredients(session, membership, recipe_id, version_number, payload)
    version = get_version(session, membership, recipe_id, version_number)
    return version_detail_response(session, version, lines)


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


@router.post(
    "/{recipe_id}/versions/{version_id}/preparation-rules",
    response_model=PreparationRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_preparation_rule_route(
    recipe_id: UUID,
    version_id: UUID,
    payload: PreparationRuleCreate,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> PreparationRuleResponse:
    return add_rule(session, membership, recipe_id, version_id, payload)


@router.delete(
    "/{recipe_id}/versions/{version_id}/preparation-rules/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_preparation_rule_route(
    recipe_id: UUID,
    version_id: UUID,
    rule_id: UUID,
    membership: HouseholdMember = Depends(get_active_household_membership),
    session: Session = Depends(get_session),
) -> None:
    delete_rule(session, membership, recipe_id, version_id, rule_id)


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
