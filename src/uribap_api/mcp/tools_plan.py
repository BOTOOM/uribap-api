from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from uribap_api.api.completion_schemas import CompletionActualLine, MealCompletionCreate
from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanEntryUpdate,
    MealPlanTransition,
)
from uribap_api.api.preparation_schemas import PreparationTaskCreate
from uribap_api.application import (
    completion_service,
    planning_service,
    preparation_service,
    recipe_service,
)
from uribap_api.application.recipe_service import normalize_recipe_name
from uribap_api.domain.planning.policies import MealPlanAction
from uribap_api.domain.preparation.policies import (
    PreparationTaskAction,
    PreparationTaskStatus,
)
from uribap_api.domain.recipes.policies import RecipeMealType
from uribap_api.mcp.runtime import McpRuntime

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)


class CompletionLineInput(BaseModel):
    """Actual consumed amount for one ingredient when completing a meal."""

    ingredient_id: str
    actual_amount: str = Field(description="Decimal string")
    unit: str


def _published_version_id(session, membership, recipe_version_id, recipe_name) -> str:
    if recipe_version_id:
        return str(recipe_version_id)
    if not recipe_name:
        raise ToolError("Pass recipe_version_id or recipe_name.")
    normalized = normalize_recipe_name(recipe_name)
    matches = [
        version
        for version, recipe in recipe_service.list_published_versions(session, membership)
        if recipe.normalized_name == normalized
    ]
    if not matches:
        raise ToolError(
            f"No published recipe named '{recipe_name}'. "
            "Create it first with uribap_create_recipe."
        )
    return str(matches[0].id)


def _plan_for_week(session, membership, week_start: date, create: bool = False):
    from uribap_api.domain.shared.errors import DomainError

    try:
        return planning_service.get_current_plan(session, membership, week_start)
    except DomainError as exc:
        if not create or exc.status_code != 404:
            raise
        result = planning_service.create_plan(
            session, membership, MealPlanCreate(week_start_date=week_start), str(uuid4())
        )
        return planning_service.get_plan(session, membership, UUID(result.payload["id"]))


def register(mcp: FastMCP, rt: McpRuntime) -> None:
    @mcp.tool(
        name="uribap_get_plan",
        annotations=READ_ONLY.model_copy(update={"title": "Weekly meal plan"}),
        description=(
            "Meal plan for a week (week_start must be a Monday, YYYY-MM-DD) with "
            "state, version and every planned entry."
        ),
    )
    def get_plan(
        ctx: Context,
        week_start: Annotated[date, Field(description="Monday of the week, e.g. 2026-09-21")],
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            plan = planning_service.get_current_plan(session, membership, week_start)
            return planning_service.plan_response(session, membership, plan)

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_add_plan_entry",
        annotations=WRITE.model_copy(update={"title": "Add meal to plan"}),
        description=(
            "Add a meal to the weekly plan. The plan is auto-created (draft) when "
            "missing. Identify the recipe by recipe_version_id or recipe_name "
            "(latest published version is used)."
        ),
    )
    def add_plan_entry(
        ctx: Context,
        week_start: Annotated[date, Field(description="Monday of the week")],
        planned_date: Annotated[date, Field(description="Day inside that week")],
        meal_type: Annotated[
            RecipeMealType, Field(description="breakfast | lunch | dinner | snack")
        ],
        servings: Annotated[int, Field(gt=0)],
        recipe_version_id: str | None = None,
        recipe_name: str | None = None,
        position: Annotated[int, Field(ge=0)] = 0,
        notes: Annotated[str | None, Field(max_length=2000)] = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            plan = _plan_for_week(session, membership, week_start, create=True)
            version_id = _published_version_id(
                session, membership, recipe_version_id, recipe_name
            )
            result = planning_service.add_entry(
                session,
                membership,
                plan.id,
                MealPlanEntryCreate(
                    expected_version=plan.version,
                    planned_date=planned_date,
                    meal_type=meal_type,
                    recipe_version_id=UUID(version_id),
                    servings=servings,
                    position=position,
                    notes=notes,
                ),
                idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_update_plan_entry",
        annotations=WRITE.model_copy(update={"title": "Update plan entry"}),
        description="Move/edit an existing plan entry (date, meal type, servings, notes).",
    )
    def update_plan_entry(
        ctx: Context,
        plan_id: Annotated[str, Field(description="Meal plan UUID")],
        entry_id: Annotated[str, Field(description="Plan entry UUID")],
        planned_date: date | None = None,
        meal_type: RecipeMealType | None = None,
        recipe_version_id: str | None = None,
        servings: Annotated[int | None, Field(gt=0)] = None,
        position: Annotated[int | None, Field(ge=0)] = None,
        notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            plan = planning_service.get_plan(session, membership, UUID(plan_id))
            result = planning_service.update_entry(
                session,
                membership,
                plan.id,
                UUID(entry_id),
                MealPlanEntryUpdate(
                    expected_version=plan.version,
                    planned_date=planned_date,
                    meal_type=meal_type,
                    recipe_version_id=UUID(recipe_version_id) if recipe_version_id else None,
                    servings=servings,
                    position=position,
                    notes=notes,
                ),
                idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_remove_plan_entry",
        annotations=DESTRUCTIVE.model_copy(update={"title": "Remove plan entry"}),
        description="Remove a meal from the plan (only while the plan is editable).",
    )
    def remove_plan_entry(
        ctx: Context,
        plan_id: Annotated[str, Field(description="Meal plan UUID")],
        entry_id: Annotated[str, Field(description="Plan entry UUID")],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            plan = planning_service.get_plan(session, membership, UUID(plan_id))
            result = planning_service.delete_entry(
                session,
                membership,
                plan.id,
                UUID(entry_id),
                expected_version=plan.version,
                idempotency_key=idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_transition_plan",
        annotations=WRITE.model_copy(update={"title": "Change plan state"}),
        description=(
            "Move the weekly plan through its lifecycle: propose | approve | "
            "reopen | archive. Reopening an approved plan requires `note`. Only "
            "approved plans feed the demand forecast."
        ),
    )
    def transition_plan(
        ctx: Context,
        week_start: Annotated[date, Field(description="Monday of the plan week")],
        action: Annotated[
            MealPlanAction, Field(description="propose | approve | reopen | archive")
        ],
        note: Annotated[str | None, Field(max_length=2000)] = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            plan = planning_service.get_current_plan(session, membership, week_start)
            result = planning_service.transition_plan(
                session,
                membership,
                plan.id,
                action,
                MealPlanTransition(expected_version=plan.version, note=note),
                idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_complete_meal",
        annotations=WRITE.model_copy(update={"title": "Mark meal as cooked"}),
        description=(
            "Record a plan entry as cooked: deducts the real stock for each "
            "ingredient. Without `lines` the recipe amounts are consumed as "
            "planned; pass lines to record actual quantities."
        ),
    )
    def complete_meal(
        ctx: Context,
        plan_id: Annotated[str, Field(description="Meal plan UUID")],
        entry_id: Annotated[str, Field(description="Plan entry UUID")],
        lines: Annotated[
            list[CompletionLineInput] | None,
            Field(description="Actual consumed amounts; omit to use recipe amounts"),
        ] = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            result = completion_service.complete_entry(
                session,
                membership,
                UUID(plan_id),
                UUID(entry_id),
                MealCompletionCreate(
                    lines=None
                    if lines is None
                    else [
                        CompletionActualLine(
                            ingredient_id=UUID(line.ingredient_id),
                            actual_amount=Decimal(line.actual_amount),
                            unit=line.unit,
                        )
                        for line in lines
                    ]
                ),
                idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_list_completions",
        annotations=READ_ONLY.model_copy(update={"title": "Meal completions"}),
        description="List recorded meal completions (optionally filtered by plan entry).",
    )
    def list_completions(
        ctx: Context,
        entry_id: Annotated[str | None, Field(description="Filter by plan entry UUID")] = None,
        state: Annotated[
            str | None, Field(description="recorded | reopened | corrected")
        ] = None,
    ) -> dict[str, Any]:
        from uribap_api.domain.completion.policies import MealCompletionState

        return rt.call(
            ctx,
            lambda session, membership, _p: {
                "items": completion_service.list_completions(
                    session,
                    membership,
                    UUID(entry_id) if entry_id else None,
                    MealCompletionState(state) if state else None,
                    None,
                    None,
                )
            },
        )

    @mcp.tool(
        name="uribap_reopen_completion",
        annotations=WRITE.model_copy(update={"title": "Reopen meal completion"}),
        description=(
            "Reopen a recorded completion: the consumed stock is returned to "
            "inventory. A reason is recommended."
        ),
    )
    def reopen_completion(
        ctx: Context,
        completion_id: Annotated[str, Field(description="Completion UUID")],
        reason: Annotated[str | None, Field(max_length=2000)] = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            completion = completion_service.get_completion(
                session, membership, UUID(completion_id)
            )
            result = completion_service.reopen_completion(
                session,
                membership,
                UUID(completion_id),
                expected_version=completion.version,
                reason=reason,
                idempotency_key=idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_list_preparation_tasks",
        annotations=READ_ONLY.model_copy(update={"title": "Preparation tasks"}),
        description="List preparation tasks (defrost, soak, marinate, prepare-ahead).",
    )
    def list_preparation_tasks(
        ctx: Context,
        status: Annotated[
            PreparationTaskStatus | None,
            Field(description="pending | completed | cancelled"),
        ] = None,
    ) -> dict[str, Any]:
        return rt.call(
            ctx,
            lambda session, membership, _p: {
                "items": preparation_service.list_tasks(
                    session, membership, status, None, None
                )
            },
        )

    @mcp.tool(
        name="uribap_create_preparation_task",
        annotations=WRITE.model_copy(update={"title": "Create preparation task"}),
        description=(
            "Create a manual preparation task (e.g. 'descongelar pollo'). "
            "`due_at` must be timezone-aware; amount+unit go together."
        ),
    )
    def create_preparation_task(
        ctx: Context,
        title: Annotated[str, Field(min_length=1, max_length=200)],
        due_at: Annotated[datetime, Field(description="ISO datetime with timezone")],
        instruction: Annotated[str | None, Field(max_length=2000)] = None,
        ingredient_id: str | None = None,
        amount: Annotated[str | None, Field(description="Decimal string")] = None,
        unit: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            result = preparation_service.create_manual_task(
                session,
                membership,
                PreparationTaskCreate(
                    title=title,
                    instruction=instruction,
                    due_at=due_at,
                    ingredient_id=UUID(ingredient_id) if ingredient_id else None,
                    amount=Decimal(amount) if amount else None,
                    unit=unit,
                ),
                idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)

    @mcp.tool(
        name="uribap_transition_preparation_task",
        annotations=WRITE.model_copy(update={"title": "Complete/cancel preparation task"}),
        description="Mark a preparation task as completed or cancelled.",
    )
    def transition_preparation_task(
        ctx: Context,
        task_id: Annotated[str, Field(description="Preparation task UUID")],
        action: Annotated[PreparationTaskAction, Field(description="complete | cancel")],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        def run(session, membership, _p):
            tasks = preparation_service.list_tasks(session, membership, None, None, None)
            task = next((t for t in tasks if str(t.id) == task_id), None)
            if task is None:
                raise ToolError(f"Preparation task {task_id} not found.")
            result = preparation_service.transition_task(
                session,
                membership,
                UUID(task_id),
                action,
                expected_version=task.version,
                idempotency_key=idempotency_key or str(uuid4()),
            )
            return result.payload

        return rt.call(ctx, run)
