from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import case, select

from uribap_api.api.recipe_schemas import (
    IngredientCreate,
    IngredientUpdate,
    RecipeCreate,
    RecipeRevision,
    RecipeUpdate,
    RecipeVersionIngredientsPut,
    RecipeVersionIngredientUpsert,
)
from uribap_api.application import ingredient_service, recipe_service
from uribap_api.domain.ingredients.policies import (
    UNIT_DIMENSIONS,
    IngredientDimension,
    normalize_ingredient_name,
    validate_unit_for_dimension,
)
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeVersion,
    RecipeVersionIngredient,
)
from uribap_api.mcp.runtime import McpRuntime

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)


class RecipeLineInput(BaseModel):
    """One ingredient line for a recipe."""

    ingredient_id: str | None = Field(
        default=None, description="Existing ingredient UUID (preferred when known)"
    )
    ingredient_name: str | None = Field(
        default=None,
        description="Ingredient name — resolved against the catalog, created if missing",
    )
    amount: str = Field(description="Quantity as decimal string, e.g. '200' or '1.5'")
    unit: str = Field(description="Unit: 'unit', 'g', 'kg', 'ml' or 'l'")
    optional: bool = Field(default=False, description="Whether the line is optional")


def _line_amount(line: RecipeLineInput) -> Decimal:
    try:
        amount = Decimal(line.amount)
        return RecipeVersionIngredientUpsert(
            ingredient_id=UUID(int=0),
            amount=amount,
            unit=line.unit,
            optional=line.optional,
        ).amount
    except (InvalidOperation, ValueError, ValidationError) as exc:
        raise ToolError(str(exc)) from exc


def _resolve_lines(
    session, membership, lines: list[RecipeLineInput]
) -> list[tuple[RecipeLineInput, Ingredient | None, IngredientDimension]]:
    resolved: list[tuple[RecipeLineInput, Ingredient | None, IngredientDimension]] = []
    pending_dimensions: dict[str, IngredientDimension] = {}
    for line in lines:
        has_id = line.ingredient_id is not None
        has_name = bool(line.ingredient_name)
        if has_id == has_name:
            raise ToolError("Each line needs exactly one of ingredient_id or ingredient_name.")
        _line_amount(line)
        if has_id:
            try:
                ingredient_id = UUID(line.ingredient_id or "")
            except ValueError as exc:
                raise ToolError(f"Invalid ingredient UUID '{line.ingredient_id}'.") from exc
            ingredient = ingredient_service.get_ingredient(session, membership, ingredient_id)
            try:
                validate_unit_for_dimension(ingredient.dimension, line.unit)
            except ValueError as exc:
                allowed = "|".join(
                    unit
                    for unit, dimension in UNIT_DIMENSIONS.items()
                    if dimension == ingredient.dimension
                )
                raise ToolError(
                    f"Unit '{line.unit}' does not match ingredient '{ingredient.name}'; "
                    f"allowed units: {allowed}."
                ) from exc
            resolved.append((line, ingredient, ingredient.dimension))
            continue

        try:
            normalized_name = normalize_ingredient_name(line.ingredient_name or "")
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        ingredient = ingredient_service.find_by_name(
            session, membership, line.ingredient_name or ""
        )
        if ingredient is not None:
            try:
                validate_unit_for_dimension(ingredient.dimension, line.unit)
            except ValueError as exc:
                allowed = "|".join(
                    unit
                    for unit, dimension in UNIT_DIMENSIONS.items()
                    if dimension == ingredient.dimension
                )
                raise ToolError(
                    f"Unit '{line.unit}' does not match ingredient '{ingredient.name}'; "
                    f"allowed units: {allowed}."
                ) from exc
            resolved.append((line, ingredient, ingredient.dimension))
            continue

        dimension = UNIT_DIMENSIONS.get(line.unit)
        if dimension is None:
            raise ToolError(
                f"Cannot auto-create '{line.ingredient_name}': unknown unit '{line.unit}'."
            )
        previous_dimension = pending_dimensions.get(normalized_name)
        if previous_dimension is not None and previous_dimension != dimension:
            raise ToolError(
                f"Ingredient '{line.ingredient_name}' is listed with incompatible dimensions."
            )
        pending_dimensions[normalized_name] = dimension
        resolved.append((line, None, dimension))
    return resolved


def _create_resolved_lines(
    session,
    membership,
    resolved: list[tuple[RecipeLineInput, Ingredient | None, IngredientDimension]],
) -> tuple[list[RecipeVersionIngredientUpsert], list[str]]:
    created_by_name: dict[str, Ingredient] = {}
    created_names: list[str] = []
    items: list[RecipeVersionIngredientUpsert] = []
    for line, ingredient, dimension in resolved:
        if ingredient is None:
            normalized_name = normalize_ingredient_name(line.ingredient_name or "")
            ingredient = created_by_name.get(normalized_name)
            if ingredient is None:
                ingredient = ingredient_service.create_ingredient(
                    session,
                    membership,
                    IngredientCreate(
                        name=line.ingredient_name or "",
                        dimension=dimension,
                        base_unit=line.unit,
                    ),
                    commit=False,
                )
                created_by_name[normalized_name] = ingredient
                created_names.append(ingredient.name)
        items.append(
            RecipeVersionIngredientUpsert(
                ingredient_id=ingredient.id,
                amount=_line_amount(line),
                unit=line.unit,
                optional=line.optional,
            )
        )
    return items, created_names


def _ingredient_row(ingredient: Ingredient) -> dict:
    return {
        "id": str(ingredient.id),
        "name": ingredient.name,
        "category": ingredient.category,
        "dimension": ingredient.dimension.value,
        "base_unit": ingredient.base_unit,
        "package_size_amount": ingredient.package_size_amount,
        "package_size_unit": ingredient.package_size_unit,
        "scope": "global" if ingredient.household_id is None else "household",
    }


def _version_lines(session, version: RecipeVersion) -> list[dict]:
    rows = session.execute(
        select(RecipeVersionIngredient, Ingredient.name)
        .join(Ingredient, Ingredient.id == RecipeVersionIngredient.ingredient_id)
        .where(RecipeVersionIngredient.recipe_version_id == version.id)
        .order_by(RecipeVersionIngredient.position, RecipeVersionIngredient.id)
    ).all()
    return [
        {
            "ingredient_id": str(line.ingredient_id),
            "ingredient_name": name,
            "amount": line.amount,
            "unit": line.unit,
            "optional": line.optional,
        }
        for line, name in rows
    ]


def register(mcp: FastMCP, rt: McpRuntime) -> None:
    @mcp.tool(
        name="uribap_list_ingredients",
        annotations=READ_ONLY.model_copy(update={"title": "List ingredients"}),
        description=(
            "List the ingredient catalog (household + global). Filter with `query` "
            "(name substring) or `dimension` (count|mass|volume)."
        ),
    )
    def list_ingredients(
        ctx: Context,
        query: Annotated[str | None, Field(description="Name filter (substring)")] = None,
        dimension: Annotated[
            IngredientDimension | None,
            Field(description="Filter by dimension: count, mass or volume"),
        ] = None,
        include_global: Annotated[
            bool, Field(description="Include global catalog ingredients")
        ] = True,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            rows = [
                _ingredient_row(i)
                for i in ingredient_service.list_ingredients(
                    session,
                    membership,
                    query,
                    dimension.value if dimension else None,
                    include_global,
                    limit,
                )
            ]
            return {"count": len(rows), "items": rows}

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_create_ingredient",
        annotations=WRITE.model_copy(update={"title": "Create ingredient"}),
        description=(
            "Create a household ingredient. `base_unit` must match `dimension`: "
            "count→unit, mass→g|kg, volume→ml|l."
        ),
    )
    def create_ingredient(
        ctx: Context,
        name: Annotated[str, Field(min_length=1, max_length=160)],
        dimension: Annotated[
            IngredientDimension, Field(description="count | mass | volume")
        ],
        base_unit: Annotated[str, Field(description="unit | g | kg | ml | l")],
        category: Annotated[str | None, Field(description="Free-form category")] = None,
        package_size_amount: Annotated[
            str | None, Field(description="Decimal string, e.g. '500'")
        ] = None,
        package_size_unit: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            ingredient = ingredient_service.create_ingredient(
                session,
                membership,
                IngredientCreate(
                    name=name,
                    category=category,
                    dimension=dimension,
                    base_unit=base_unit,
                    package_size_amount=package_size_amount,
                    package_size_unit=package_size_unit,
                ),
            )
            return _ingredient_row(ingredient)

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_update_ingredient",
        annotations=WRITE.model_copy(update={"title": "Update ingredient"}),
        description="Rename a household ingredient or change its category.",
    )
    def update_ingredient(
        ctx: Context,
        ingredient_id: Annotated[str, Field(description="Ingredient UUID")],
        name: str | None = None,
        category: str | None = None,
    ) -> dict[str, Any]:
        return rt.call(
            ctx,
            lambda session, membership, _p: _ingredient_row(
                ingredient_service.update_ingredient(
                    session,
                    membership,
                    UUID(ingredient_id),
                    IngredientUpdate(name=name, category=category),
                )
            ),
        )

    @mcp.tool(
        name="uribap_archive_ingredient",
        annotations=DESTRUCTIVE.model_copy(update={"title": "Archive ingredient"}),
        description=(
            "Archive a household ingredient (soft delete). Existing lots and recipe "
            "lines keep working; the ingredient stops appearing in pickers."
        ),
    )
    def archive_ingredient(
        ctx: Context,
        ingredient_id: Annotated[str, Field(description="Ingredient UUID")],
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            ingredient_service.archive_ingredient(session, membership, UUID(ingredient_id))
            return {"archived": ingredient_id}

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_list_recipes",
        annotations=READ_ONLY.model_copy(update={"title": "List recipes"}),
        description="List household recipes with their latest version summary.",
    )
    def list_recipes(
        ctx: Context,
        query: Annotated[str | None, Field(description="Name filter (substring)")] = None,
        include_archived: bool = False,
        limit: Annotated[int, Field(ge=1, le=100)] = 50,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            rows = recipe_service.list_recipes(
                session, membership, query, include_archived, limit
            )
            return {
                "items": [
                    {
                        "id": str(recipe.id),
                        "name": recipe.name,
                        "description": recipe.description,
                        "archived": recipe.archived_at is not None,
                        "latest_version": None
                        if version is None
                        else {
                            "recipe_version_id": str(version.id),
                            "version_number": version.version_number,
                            "state": version.state.value,
                            "base_servings": version.base_servings,
                            "prep_minutes": version.prep_minutes,
                        },
                    }
                    for recipe, version in rows
                ]
            }

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_get_recipe",
        annotations=READ_ONLY.model_copy(update={"title": "Recipe detail"}),
        description=(
            "Full recipe detail: all versions plus the ingredient lines of the "
            "latest version."
        ),
    )
    def get_recipe(
        ctx: Context,
        recipe_id: Annotated[str | None, Field(description="Recipe UUID")] = None,
        recipe_name: Annotated[str | None, Field(description="Exact recipe name")] = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            if (recipe_id is None) == (recipe_name is None):
                raise ToolError("Provide exactly one of recipe_id or recipe_name.")
            if recipe_id is not None:
                try:
                    recipe_uuid = UUID(recipe_id)
                except ValueError as exc:
                    raise ToolError(f"Invalid recipe UUID '{recipe_id}'.") from exc
                recipe = recipe_service.get_recipe(session, membership, recipe_uuid)
            else:
                normalized_name = recipe_service.normalize_recipe_name(recipe_name or "")
                candidates = list(
                    session.scalars(
                        select(Recipe)
                        .where(
                            Recipe.household_id == membership.household_id,
                            Recipe.normalized_name == normalized_name,
                        )
                        .order_by(
                            case((Recipe.archived_at.is_(None), 0), else_=1),
                            Recipe.id,
                        )
                    )
                )
                active = [candidate for candidate in candidates if candidate.archived_at is None]
                if len(active) > 1:
                    ids = ", ".join(str(candidate.id) for candidate in active)
                    raise ToolError(
                        f"Multiple active recipes named '{recipe_name}' found; "
                        f"candidate IDs: {ids}."
                    )
                if active:
                    recipe = active[0]
                elif len(candidates) > 1:
                    ids = ", ".join(str(candidate.id) for candidate in candidates)
                    raise ToolError(
                        f"Multiple archived recipes named '{recipe_name}' found; "
                        f"candidate IDs: {ids}."
                    )
                elif candidates:
                    recipe = candidates[0]
                else:
                    raise ToolError(f"Recipe '{recipe_name}' not found.")
            versions = list(
                session.scalars(
                    select(RecipeVersion)
                    .where(RecipeVersion.recipe_id == recipe.id)
                    .order_by(RecipeVersion.version_number.desc())
                )
            )
            latest = versions[0] if versions else None
            summaries = [
                {
                    "recipe_version_id": str(version.id),
                    "version_number": version.version_number,
                    "state": version.state.value,
                    "base_servings": version.base_servings,
                    "prep_minutes": version.prep_minutes,
                    "published_at": version.published_at,
                }
                for version in versions
            ]
            active_version = next(
                (summary for summary in summaries if summary["state"] == "published"),
                None,
            )
            return {
                "id": str(recipe.id),
                "name": recipe.name,
                "description": recipe.description,
                "archived": recipe.archived_at is not None,
                "active_version": active_version,
                "versions": summaries,
                "ingredients_version_number": latest.version_number if latest else None,
                "ingredients": [] if latest is None else _version_lines(session, latest),
            }

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_create_recipe",
        annotations=WRITE.model_copy(update={"title": "Create and publish recipe"}),
        description=(
            "Create a recipe end to end: draft version 1, ingredient lines and "
            "publish. Each line accepts `ingredient_id` OR `ingredient_name` — "
            "names are matched against the catalog and auto-created when missing "
            "(dimension is inferred from the unit). Set publish=false to keep a draft."
        ),
    )
    def create_recipe(
        ctx: Context,
        name: Annotated[str, Field(min_length=1, max_length=200)],
        ingredients: Annotated[
            list[RecipeLineInput],
            Field(max_length=100, description="Ingredient lines; at most 100"),
        ],
        description: str | None = None,
        base_servings: Annotated[int, Field(gt=0)] = 4,
        prep_minutes: Annotated[int, Field(ge=0)] = 0,
        publish: Annotated[
            bool, Field(description="Publish immediately so the recipe can be planned")
        ] = True,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            normalized_name = recipe_service.normalize_recipe_name(name)
            existing = session.scalar(
                select(Recipe).where(
                    Recipe.household_id == membership.household_id,
                    Recipe.normalized_name == normalized_name,
                    Recipe.archived_at.is_(None),
                )
            )
            if existing is not None:
                raise ToolError(
                    f"Recipe '{name}' already exists (id {existing.id}). "
                    "Use uribap_update_recipe to change it."
                )
            recipe_payload = RecipeCreate(
                name=name,
                description=description,
                base_servings=base_servings,
                prep_minutes=prep_minutes,
            )
            resolved = _resolve_lines(session, membership, ingredients)
            items, created_ingredients = _create_resolved_lines(session, membership, resolved)
            recipe = recipe_service.create_recipe(
                session,
                membership,
                recipe_payload,
                commit=False,
            )
            recipe_service.replace_version_ingredients(
                session,
                membership,
                recipe.id,
                1,
                RecipeVersionIngredientsPut(items=items),
                commit=False,
            )
            version = recipe_service.get_version(session, membership, recipe.id, 1)
            published = False
            if publish:
                recipe_service.publish_version(
                    session, membership, recipe.id, 1, commit=False
                )
                published = True
            session.commit()
            return {
                "recipe_id": str(recipe.id),
                "name": recipe.name,
                "version_number": 1,
                "recipe_version_id": str(version.id),
                "published": published,
                "ingredient_lines": len(items),
                "auto_created_ingredients": created_ingredients,
            }

        return rt.call(ctx, run)


    @mcp.tool(
        name="uribap_update_recipe",
        annotations=WRITE.model_copy(update={"title": "Update recipe"}),
        description=(
            "Edit name and description in place. Changing base_servings, prep_minutes or "
            "ingredients creates a new version (or edits the pending draft) cloned from the "
            "latest version; ingredients replaces the whole list. publish makes it active and "
            "archives the previous published version. Planned and cooked meal history is preserved."
        ),
    )
    def update_recipe(
        ctx: Context,
        recipe_id: Annotated[str, Field(description="Recipe UUID")],
        name: Annotated[str | None, Field(min_length=1, max_length=200)] = None,
        description: Annotated[
            str | None, Field(description="Empty string clears description")
        ] = None,
        base_servings: Annotated[int | None, Field(gt=0)] = None,
        prep_minutes: Annotated[int | None, Field(ge=0)] = None,
        ingredients: Annotated[
            list[RecipeLineInput] | None,
            Field(
                max_length=100,
                description=(
                    "Replacement ingredient list (up to 100); omitted means "
                    "keep current lines"
                ),
            ),
        ] = None,
        publish: Annotated[bool, Field(description="Publish the revised version")] = True,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            metadata: dict[str, Any] = {}
            if name is not None:
                metadata["name"] = name
            if description is not None:
                metadata["description"] = None if description == "" else description
            has_content = (
                base_servings is not None
                or prep_minutes is not None
                or ingredients is not None
            )
            if not metadata and not has_content:
                raise ToolError("Provide at least one recipe field to update.")
            try:
                recipe_uuid = UUID(recipe_id)
            except ValueError as exc:
                raise ToolError(f"Invalid recipe UUID '{recipe_id}'.") from exc

            existing_recipe = recipe_service.get_recipe(session, membership, recipe_uuid)
            if existing_recipe.archived_at is not None:
                detail = (
                    "Archived recipes cannot be revised."
                    if has_content
                    else "Archived recipes cannot be edited."
                )
                raise DomainError("conflict", "Recipe archived", detail, 409)

            try:
                revision = (
                    RecipeRevision(
                        base_servings=base_servings,
                        prep_minutes=prep_minutes,
                        items=None,
                        publish=publish,
                    )
                    if has_content
                    else None
                )
                update = RecipeUpdate(**metadata) if metadata else None
            except ValidationError as exc:
                raise ToolError(str(exc)) from exc

            resolved = (
                _resolve_lines(session, membership, ingredients)
                if ingredients is not None
                else None
            )
            revision_items, auto_created_ingredients = (
                _create_resolved_lines(session, membership, resolved)
                if resolved is not None
                else (None, [])
            )
            if revision is not None and revision_items is not None:
                revision = revision.model_copy(update={"items": revision_items})

            if has_content:
                assert revision is not None
                version = recipe_service.revise_recipe(
                    session,
                    membership,
                    recipe_uuid,
                    revision,
                    commit=False,
                )
            else:
                version = None
            recipe = (
                recipe_service.update_recipe(
                    session,
                    membership,
                    recipe_uuid,
                    update,
                    commit=False,
                )
                if update is not None
                else recipe_service.get_recipe(session, membership, recipe_uuid)
            )
            if version is None:
                version = session.scalar(
                    select(RecipeVersion)
                    .where(RecipeVersion.recipe_id == recipe.id)
                    .order_by(RecipeVersion.version_number.desc())
                )
            session.commit()
            return {
                "recipe_id": str(recipe.id),
                "name": recipe.name,
                "description": recipe.description,
                "archived": recipe.archived_at is not None,
                "version_number": version.version_number if version else None,
                "recipe_version_id": str(version.id) if version else None,
                "state": version.state.value if version else None,
                "ingredients": [] if version is None else _version_lines(session, version),
                "auto_created_ingredients": auto_created_ingredients,
            }

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_archive_recipe",
        annotations=DESTRUCTIVE.model_copy(update={"title": "Archive recipe"}),
        description="Archive a recipe without deleting its planned or cooked meal history.",
    )
    def archive_recipe(
        ctx: Context,
        recipe_id: Annotated[str, Field(description="Recipe UUID")],
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            try:
                recipe_uuid = UUID(recipe_id)
            except ValueError as exc:
                raise ToolError(f"Invalid recipe UUID '{recipe_id}'.") from exc
            recipe = recipe_service.archive_recipe(session, membership, recipe_uuid)
            return {
                "recipe_id": str(recipe.id),
                "name": recipe.name,
                "archived": recipe.archived_at is not None,
            }

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_unarchive_recipe",
        annotations=WRITE.model_copy(update={"title": "Unarchive recipe"}),
        description="Restore an archived recipe to the active recipe list.",
    )
    def unarchive_recipe(
        ctx: Context,
        recipe_id: Annotated[str, Field(description="Recipe UUID")],
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            try:
                recipe_uuid = UUID(recipe_id)
            except ValueError as exc:
                raise ToolError(f"Invalid recipe UUID '{recipe_id}'.") from exc
            recipe = recipe_service.unarchive_recipe(session, membership, recipe_uuid)
            return {
                "recipe_id": str(recipe.id),
                "name": recipe.name,
                "archived": recipe.archived_at is not None,
            }

        return rt.call(ctx, run)
