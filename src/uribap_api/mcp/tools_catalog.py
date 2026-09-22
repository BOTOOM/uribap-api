from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from sqlalchemy import select

from uribap_api.api.recipe_schemas import (
    IngredientCreate,
    IngredientUpdate,
    RecipeCreate,
    RecipeVersionIngredientsPut,
    RecipeVersionIngredientUpsert,
)
from uribap_api.application import ingredient_service, recipe_service
from uribap_api.domain.ingredients.policies import (
    UNIT_DIMENSIONS,
    IngredientDimension,
    normalize_ingredient_name,
)
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.recipe_models import (
    RecipeVersion,
    RecipeVersionIngredient,
)
from uribap_api.mcp.runtime import McpRuntime

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)


class RecipeLineInput(BaseModel):
    """One ingredient line for `uribap_create_recipe`."""

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
        recipe_id: Annotated[str, Field(description="Recipe UUID")],
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            recipe = recipe_service.get_recipe(session, membership, UUID(recipe_id))
            versions = list(
                session.scalars(
                    select(RecipeVersion)
                    .where(RecipeVersion.recipe_id == recipe.id)
                    .order_by(RecipeVersion.version_number.desc())
                )
            )
            latest = versions[0] if versions else None
            return {
                "id": str(recipe.id),
                "name": recipe.name,
                "description": recipe.description,
                "archived": recipe.archived_at is not None,
                "versions": [
                    {
                        "recipe_version_id": str(v.id),
                        "version_number": v.version_number,
                        "state": v.state.value,
                        "base_servings": v.base_servings,
                        "prep_minutes": v.prep_minutes,
                    }
                    for v in versions
                ],
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
            Field(description="Ingredient lines; at least one is recommended"),
        ],
        description: str | None = None,
        base_servings: Annotated[int, Field(gt=0)] = 4,
        prep_minutes: Annotated[int, Field(ge=0)] = 0,
        publish: Annotated[
            bool, Field(description="Publish immediately so the recipe can be planned")
        ] = True,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            recipe = recipe_service.create_recipe(
                session,
                membership,
                RecipeCreate(
                    name=name,
                    description=description,
                    base_servings=base_servings,
                    prep_minutes=prep_minutes,
                ),
            )
            created_ingredients: list[str] = []
            items: list[RecipeVersionIngredientUpsert] = []
            for line in ingredients:
                ingredient, created = _resolve_ingredient(session, membership, line)
                if created:
                    created_ingredients.append(ingredient.name)
                items.append(
                    RecipeVersionIngredientUpsert(
                        ingredient_id=ingredient.id,
                        amount=Decimal(line.amount),
                        unit=line.unit,
                        optional=line.optional,
                    )
                )
            recipe_service.replace_version_ingredients(
                session, membership, recipe.id, 1, RecipeVersionIngredientsPut(items=items)
            )
            version = recipe_service.get_version(session, membership, recipe.id, 1)
            published = False
            if publish:
                recipe_service.publish_version(session, membership, recipe.id, 1)
                published = True
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


def _resolve_ingredient(
    session, membership, line: RecipeLineInput
) -> tuple[Ingredient, bool]:
    """Resolve a recipe line to an ingredient; returns (ingredient, was_created)."""
    if line.ingredient_id:
        ingredient = session.get(Ingredient, UUID(line.ingredient_id))
        if ingredient is None or ingredient.archived_at is not None:
            raise ToolError(f"Ingredient {line.ingredient_id} not found.")
        return ingredient, False
    if not line.ingredient_name:
        raise ToolError("Each line needs ingredient_id or ingredient_name.")
    normalized = normalize_ingredient_name(line.ingredient_name)
    for candidate in ingredient_service.list_ingredients(
        session, membership, line.ingredient_name, None, True, 100
    ):
        if candidate.normalized_name == normalized:
            return candidate, False
    dimension = UNIT_DIMENSIONS.get(line.unit)
    if dimension is None:
        raise ToolError(
            f"Cannot auto-create '{line.ingredient_name}': unknown unit '{line.unit}'."
        )
    ingredient = ingredient_service.create_ingredient(
        session,
        membership,
        IngredientCreate(
            name=line.ingredient_name.strip(),
            dimension=dimension,
            base_unit=line.unit,
        ),
    )
    return ingredient, True
