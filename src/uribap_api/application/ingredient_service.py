import base64
import binascii
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, case, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.recipe_schemas import IngredientCreate, IngredientUpdate
from uribap_api.domain.ingredients.policies import normalize_ingredient_name
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient


@dataclass(frozen=True, slots=True)
class IngredientPageResult:
    items: list[Ingredient]
    next_cursor: str | None


def _encode_ingredient_cursor(normalized_name: str, ingredient_id: UUID) -> str:
    payload = json.dumps(
        {"n": normalized_name, "id": str(ingredient_id)},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_ingredient_cursor(cursor: str) -> tuple[str, UUID]:
    try:
        if len(cursor) > 1024 or not re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", cursor):
            raise ValueError
        encoded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(
            base64.b64decode(encoded, altchars=b"-_", validate=True).decode("utf-8")
        )
        if not isinstance(payload, dict) or payload.keys() != {"n", "id"}:
            raise ValueError
        normalized_name = payload["n"]
        raw_id = payload["id"]
        if (
            not isinstance(normalized_name, str)
            or len(normalized_name) > 160
            or not isinstance(raw_id, str)
        ):
            raise ValueError
        return normalized_name, UUID(raw_id)
    except (binascii.Error, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise DomainError(
            "validation_error",
            "Invalid ingredient cursor",
            "The ingredient cursor is invalid.",
            422,
        ) from exc


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
    *,
    cursor: str | None = None,
) -> IngredientPageResult:
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
    if cursor is not None:
        cursor_name, cursor_id = _decode_ingredient_cursor(cursor)
        statement = statement.where(
            or_(
                Ingredient.normalized_name > cursor_name,
                and_(
                    Ingredient.normalized_name == cursor_name,
                    Ingredient.id > cursor_id,
                ),
            )
        )
    page_limit = min(limit, 100)
    rows = list(
        session.scalars(
            statement.order_by(Ingredient.normalized_name, Ingredient.id).limit(page_limit + 1)
        )
    )
    has_next_page = len(rows) > page_limit
    items = rows[:page_limit]
    next_cursor = (
        _encode_ingredient_cursor(items[-1].normalized_name, items[-1].id)
        if has_next_page
        else None
    )
    return IngredientPageResult(items=items, next_cursor=next_cursor)


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
