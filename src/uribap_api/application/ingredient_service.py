from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.recipe_schemas import IngredientCreate, IngredientUpdate
from uribap_api.domain.ingredients.policies import normalize_ingredient_name
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient


def create_ingredient(
    session: Session,
    membership: HouseholdMember,
    payload: IngredientCreate,
    *,
    commit: bool = True,
) -> Ingredient:
    ingredient = Ingredient(
        household_id=membership.household_id,
        name=payload.name,
        normalized_name=normalize_ingredient_name(payload.name),
        category=payload.category,
        dimension=payload.dimension,
        base_unit=payload.base_unit,
        pantry_staple=payload.pantry_staple,
        package_size_amount=float(payload.package_size_amount)
        if payload.package_size_amount
        else None,
        package_size_unit=payload.package_size_unit,
        created_by_user_id=membership.user_id,
    )
    if commit:
        session.add(ingredient)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise DomainError(
                "conflict", "Ingredient conflict", "The ingredient already exists.", 409
            ) from exc
        session.refresh(ingredient)
        return ingredient
    try:
        with session.begin_nested():
            session.add(ingredient)
            session.flush()
    except IntegrityError as exc:
        raise DomainError(
            "conflict", "Ingredient conflict", "The ingredient already exists.", 409
        ) from exc
    return ingredient


def find_by_name(session: Session, membership: HouseholdMember, name: str) -> Ingredient | None:
    normalized_name = normalize_ingredient_name(name)
    statement = (
        select(Ingredient)
        .where(
            Ingredient.normalized_name == normalized_name,
            Ingredient.archived_at.is_(None),
            or_(
                Ingredient.household_id == membership.household_id,
                Ingredient.household_id.is_(None),
            ),
        )
        .order_by(
            case((Ingredient.household_id == membership.household_id, 0), else_=1),
            Ingredient.id,
        )
        .limit(1)
    )
    return session.scalar(statement)


def list_ingredients(
    session: Session,
    membership: HouseholdMember,
    query: str | None,
    dimension: str | None,
    include_global: bool,
    limit: int,
) -> list[Ingredient]:
    scopes = [Ingredient.household_id == membership.household_id]
    if include_global:
        scopes.append(Ingredient.household_id.is_(None))
    statement = select(Ingredient).where(or_(*scopes), Ingredient.archived_at.is_(None))
    if query:
        statement = statement.where(
            Ingredient.normalized_name.ilike(f"%{normalize_ingredient_name(query)}%")
        )
    if dimension:
        statement = statement.where(Ingredient.dimension == dimension)
    return list(
        session.scalars(statement.order_by(Ingredient.normalized_name).limit(min(limit, 100)))
    )


def get_ingredient(
    session: Session, membership: HouseholdMember, ingredient_id: UUID
) -> Ingredient:
    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None or ingredient.archived_at is not None:
        raise DomainError(
            "not_found", "Ingredient not found", "The ingredient could not be found.", 404
        )
    if ingredient.household_id not in {None, membership.household_id}:
        raise DomainError(
            "forbidden",
            "Permission denied",
            "The ingredient is not available to this household.",
            403,
        )
    return ingredient


def update_ingredient(
    session: Session,
    membership: HouseholdMember,
    ingredient_id: UUID,
    payload: IngredientUpdate,
) -> Ingredient:
    ingredient = get_ingredient(session, membership, ingredient_id)
    if ingredient.household_id is None:
        raise DomainError(
            "forbidden", "Permission denied", "Global ingredients are read-only.", 403
        )
    if payload.name is not None:
        ingredient.name = payload.name
        ingredient.normalized_name = normalize_ingredient_name(payload.name)
    if payload.category is not None:
        ingredient.category = payload.category
    if payload.pantry_staple is not None:
        ingredient.pantry_staple = payload.pantry_staple
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict", "Ingredient conflict", "The ingredient already exists.", 409
        ) from exc
    session.refresh(ingredient)
    return ingredient


def archive_ingredient(session: Session, membership: HouseholdMember, ingredient_id: UUID) -> None:
    ingredient = get_ingredient(session, membership, ingredient_id)
    if ingredient.household_id is None:
        raise DomainError(
            "forbidden", "Permission denied", "Global ingredients are read-only.", 403
        )
    ingredient.archived_at = datetime.now(UTC)
    session.commit()
