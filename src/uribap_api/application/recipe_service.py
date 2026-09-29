from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from uribap_api.api.recipe_schemas import (
    RecipeCreate,
    RecipeRevision,
    RecipeUpdate,
    RecipeVersionCreate,
    RecipeVersionIngredientsPut,
    RecipeVersionIngredientUpsert,
)
from uribap_api.domain.ingredients.policies import validate_unit_for_dimension
from uribap_api.domain.recipes.policies import (
    RecipeVersionState,
    can_publish_version,
    validate_servings,
)
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeFavorite,
    RecipeVersion,
    RecipeVersionIngredient,
)


def normalize_recipe_name(value: str) -> str:
    return " ".join(value.casefold().split())


def create_recipe(session: Session, membership: HouseholdMember, payload: RecipeCreate) -> Recipe:
    recipe = Recipe(
        household_id=membership.household_id,
        name=payload.name,
        normalized_name=normalize_recipe_name(payload.name),
        description=payload.description,
        created_by_user_id=membership.user_id,
    )
    session.add(recipe)
    session.flush()
    session.add(
        RecipeVersion(
            recipe_id=recipe.id,
            version_number=1,
            base_servings=validate_servings(payload.base_servings),
            prep_minutes=payload.prep_minutes,
            state=RecipeVersionState.DRAFT,
            created_by_user_id=membership.user_id,
        )
    )
    session.commit()
    session.refresh(recipe)
    return recipe


def list_recipes(
    session: Session,
    membership: HouseholdMember,
    query: str | None,
    archived: bool,
    limit: int,
) -> list[tuple[Recipe, RecipeVersion | None]]:
    statement = select(Recipe).where(Recipe.household_id == membership.household_id)
    if not archived:
        statement = statement.where(Recipe.archived_at.is_(None))
    if query:
        statement = statement.where(
            Recipe.normalized_name.ilike(f"%{normalize_recipe_name(query)}%")
        )
    recipes = list(
        session.scalars(statement.order_by(Recipe.normalized_name).limit(min(limit, 100)))
    )
    return [
        (
            recipe,
            session.scalar(
                select(RecipeVersion)
                .where(RecipeVersion.recipe_id == recipe.id)
                .order_by(desc(RecipeVersion.version_number))
                .limit(1)
            ),
        )
        for recipe in recipes
    ]


def list_published_versions(
    session: Session, membership: HouseholdMember
) -> list[tuple[RecipeVersion, Recipe]]:
    statement = (
        select(RecipeVersion, Recipe)
        .join(Recipe, Recipe.id == RecipeVersion.recipe_id)
        .where(
            Recipe.household_id == membership.household_id,
            Recipe.archived_at.is_(None),
            RecipeVersion.state == RecipeVersionState.PUBLISHED,
        )
        .order_by(Recipe.normalized_name, desc(RecipeVersion.version_number))
    )
    rows = session.execute(statement).all()
    return [(row[0], row[1]) for row in rows]


def get_recipe(session: Session, membership: HouseholdMember, recipe_id: UUID) -> Recipe:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None or recipe.household_id != membership.household_id:
        raise DomainError("not_found", "Recipe not found", "The recipe could not be found.", 404)
    return recipe


def _get_recipe_for_update(
    session: Session, membership: HouseholdMember, recipe_id: UUID
) -> Recipe:
    recipe = session.scalar(
        select(Recipe).where(Recipe.id == recipe_id).with_for_update()
    )
    if recipe is None or recipe.household_id != membership.household_id:
        raise DomainError("not_found", "Recipe not found", "The recipe could not be found.", 404)
    return recipe


def update_recipe(
    session: Session,
    membership: HouseholdMember,
    recipe_id: UUID,
    payload: RecipeUpdate,
) -> Recipe:
    recipe = get_recipe(session, membership, recipe_id)
    if recipe.archived_at is not None:
        raise DomainError(
            "conflict", "Recipe archived", "Archived recipes cannot be edited.", 409
        )
    if "name" in payload.model_fields_set and payload.name is not None:
        recipe.name = payload.name
        recipe.normalized_name = normalize_recipe_name(payload.name)
    if "description" in payload.model_fields_set:
        recipe.description = payload.description
    session.commit()
    session.refresh(recipe)
    return recipe


def create_version(
    session: Session,
    membership: HouseholdMember,
    recipe_id: UUID,
    payload: RecipeVersionCreate,
) -> RecipeVersion:
    recipe = get_recipe(session, membership, recipe_id)
    latest_number = (
        session.scalar(
            select(RecipeVersion.version_number)
            .where(RecipeVersion.recipe_id == recipe.id)
            .order_by(desc(RecipeVersion.version_number))
            .limit(1)
        )
        or 0
    )
    version = RecipeVersion(
        recipe_id=recipe.id,
        version_number=latest_number + 1,
        base_servings=validate_servings(payload.base_servings),
        prep_minutes=payload.prep_minutes,
        state=RecipeVersionState.DRAFT,
        created_by_user_id=membership.user_id,
    )
    session.add(version)
    session.commit()
    session.refresh(version)
    return version


def get_version(
    session: Session, membership: HouseholdMember, recipe_id: UUID, version_number: int
) -> RecipeVersion:
    recipe = get_recipe(session, membership, recipe_id)
    version = session.scalar(
        select(RecipeVersion).where(
            RecipeVersion.recipe_id == recipe.id,
            RecipeVersion.version_number == version_number,
        )
    )
    if version is None:
        raise DomainError(
            "not_found", "Recipe version not found", "The recipe version could not be found.", 404
        )
    return version


def list_version_ingredients(
    session: Session, version: RecipeVersion
) -> list[RecipeVersionIngredient]:
    return list(
        session.scalars(
            select(RecipeVersionIngredient)
            .where(RecipeVersionIngredient.recipe_version_id == version.id)
            .order_by(RecipeVersionIngredient.position, RecipeVersionIngredient.id)
        )
    )


def replace_version_ingredients(
    session: Session,
    membership: HouseholdMember,
    recipe_id: UUID,
    version_number: int,
    payload: RecipeVersionIngredientsPut,
) -> list[RecipeVersionIngredient]:
    version = get_version(session, membership, recipe_id, version_number)
    if version.state != RecipeVersionState.DRAFT:
        raise DomainError(
            "conflict",
            "Recipe version conflict",
            "Only draft versions can be edited.",
            409,
        )
    validated = _validated_lines(session, membership, payload.items)
    _replace_lines(session, version, validated)
    session.commit()
    return list_version_ingredients(session, version)


def _validated_lines(
    session: Session,
    membership: HouseholdMember,
    items: list[RecipeVersionIngredientUpsert],
) -> list[RecipeVersionIngredientUpsert]:
    ingredient_ids = {item.ingredient_id for item in items}
    ingredients = (
        {
            row.id: row
            for row in session.scalars(
                select(Ingredient).where(Ingredient.id.in_(ingredient_ids))
            ).all()
        }
        if ingredient_ids
        else {}
    )
    for item in items:
        ingredient = ingredients.get(item.ingredient_id)
        if (
            ingredient is None
            or ingredient.archived_at is not None
            or ingredient.household_id not in {None, membership.household_id}
        ):
            raise DomainError(
                "not_found",
                "Ingredient not found",
                "An ingredient in the list is not available to this household.",
                404,
            )
        try:
            validate_unit_for_dimension(ingredient.dimension, item.unit)
        except ValueError as exc:
            raise DomainError(
                "validation",
                "Invalid unit",
                f"The unit '{item.unit}' does not match the ingredient dimension.",
                422,
            ) from exc
    return items


def _replace_lines(
    session: Session,
    version: RecipeVersion,
    items: list[RecipeVersionIngredientUpsert],
) -> list[RecipeVersionIngredient]:
    for line in list_version_ingredients(session, version):
        session.delete(line)
    session.flush()
    lines = [
        RecipeVersionIngredient(
            recipe_version_id=version.id,
            ingredient_id=item.ingredient_id,
            amount=item.amount,
            unit=item.unit,
            position=index,
            optional=item.optional,
        )
        for index, item in enumerate(items)
    ]
    session.add_all(lines)
    return lines


def revise_recipe(
    session: Session,
    membership: HouseholdMember,
    recipe_id: UUID,
    payload: RecipeRevision,
) -> RecipeVersion:
    recipe = _get_recipe_for_update(session, membership, recipe_id)
    if recipe.archived_at is not None:
        raise DomainError(
            "conflict", "Recipe archived", "Archived recipes cannot be revised.", 409
        )
    latest = session.scalar(
        select(RecipeVersion)
        .where(RecipeVersion.recipe_id == recipe.id)
        .order_by(desc(RecipeVersion.version_number))
        .limit(1)
    )
    if latest is None:
        raise DomainError(
            "not_found", "Recipe version not found", "The recipe version could not be found.", 404
        )
    validated_items = (
        _validated_lines(session, membership, payload.items)
        if payload.items is not None
        else None
    )
    if latest.state == RecipeVersionState.DRAFT:
        version = latest
    else:
        version = RecipeVersion(
            recipe_id=recipe.id,
            version_number=latest.version_number + 1,
            base_servings=latest.base_servings,
            prep_minutes=latest.prep_minutes,
            state=RecipeVersionState.DRAFT,
            created_by_user_id=membership.user_id,
        )
        latest_lines = list_version_ingredients(session, latest)
        session.add(version)
        session.flush()
        session.add_all(
            [
                RecipeVersionIngredient(
                    recipe_version_id=version.id,
                    ingredient_id=line.ingredient_id,
                    amount=line.amount,
                    unit=line.unit,
                    optional=line.optional,
                    position=line.position,
                )
                for line in latest_lines
            ]
        )
        session.flush()
    if payload.base_servings is not None:
        version.base_servings = validate_servings(payload.base_servings)
    if payload.prep_minutes is not None:
        version.prep_minutes = payload.prep_minutes
    if validated_items is not None:
        _replace_lines(session, version, validated_items)
    if payload.publish:
        _publish(session, membership, version)
    session.commit()
    session.refresh(version)
    return version


def _publish(
    session: Session, membership: HouseholdMember, version: RecipeVersion
) -> None:
    if not can_publish_version(version.state):
        raise DomainError(
            "conflict", "Recipe version conflict", "Only draft versions can be published.", 409
        )
    version.state = RecipeVersionState.PUBLISHED
    version.published_by_user_id = membership.user_id
    version.published_at = datetime.now(UTC)
    other_published = session.scalars(
        select(RecipeVersion).where(
            RecipeVersion.recipe_id == version.recipe_id,
            RecipeVersion.id != version.id,
            RecipeVersion.state == RecipeVersionState.PUBLISHED,
        )
    )
    for previous in other_published:
        previous.state = RecipeVersionState.ARCHIVED


def publish_version(
    session: Session, membership: HouseholdMember, recipe_id: UUID, version_number: int
) -> RecipeVersion:
    version = get_version(session, membership, recipe_id, version_number)
    _publish(session, membership, version)
    session.commit()
    session.refresh(version)
    return version


def archive_recipe(session: Session, membership: HouseholdMember, recipe_id: UUID) -> Recipe:
    recipe = get_recipe(session, membership, recipe_id)
    if recipe.archived_at is None:
        recipe.archived_at = datetime.now(UTC)
    session.commit()
    session.refresh(recipe)
    return recipe


def unarchive_recipe(session: Session, membership: HouseholdMember, recipe_id: UUID) -> Recipe:
    recipe = get_recipe(session, membership, recipe_id)
    recipe.archived_at = None
    session.commit()
    session.refresh(recipe)
    return recipe


def favorite_recipe(session: Session, membership: HouseholdMember, recipe_id: UUID) -> None:
    get_recipe(session, membership, recipe_id)
    existing = session.scalar(
        select(RecipeFavorite).where(
            RecipeFavorite.user_id == membership.user_id,
            RecipeFavorite.recipe_id == recipe_id,
        )
    )
    if existing is None:
        session.add(RecipeFavorite(user_id=membership.user_id, recipe_id=recipe_id))
        session.commit()


def unfavorite_recipe(session: Session, membership: HouseholdMember, recipe_id: UUID) -> None:
    get_recipe(session, membership, recipe_id)
    favorite = session.scalar(
        select(RecipeFavorite).where(
            RecipeFavorite.user_id == membership.user_id,
            RecipeFavorite.recipe_id == recipe_id,
        )
    )
    if favorite is not None:
        session.delete(favorite)
        session.commit()
