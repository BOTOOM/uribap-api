from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.preparation_schemas import (
    PreparationRuleCreate,
    PreparationRuleResponse,
    PreparationTaskCreate,
    PreparationTaskResponse,
)
from uribap_api.application.event_service import record_event
from uribap_api.domain.events.policies import DomainEventKind
from uribap_api.domain.ingredients.policies import validate_unit_for_dimension
from uribap_api.domain.preparation.policies import (
    PreparationError,
    PreparationTaskAction,
    PreparationTaskOrigin,
    PreparationTaskStatus,
    PreparationTaskType,
    apply_task_transition,
    assert_version,
    compute_due_at,
    derived_fingerprint,
    rule_type_to_task_type,
    validate_manual_task,
)
from uribap_api.domain.recipes.policies import PreparationRuleType, RecipeVersionState
from uribap_api.domain.shared.errors import DomainError
from uribap_api.domain.shared.fingerprint import operation_fingerprint
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.planning_models import MealPlan, MealPlanEntry
from uribap_api.infrastructure.persistence.preparation_models import (
    PreparationOperation,
    PreparationTask,
)
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipePreparationRule,
    RecipeVersion,
)


@dataclass(frozen=True)
class PreparationMutationResult:
    payload: dict[str, Any]


def task_response(
    task: PreparationTask,
    entry: MealPlanEntry | None,
    recipe_name: str | None,
    ingredient_name: str | None,
) -> PreparationTaskResponse:
    return PreparationTaskResponse(
        id=task.id,
        origin=task.origin,
        task_type=task.task_type,
        title=task.title,
        instruction=task.instruction,
        due_at=task.due_at,
        status=task.status,
        version=task.version,
        meal_plan_entry_id=task.meal_plan_entry_id,
        planned_date=entry.planned_date if entry else None,
        meal_type=entry.meal_type if entry else None,
        recipe_version_id=task.recipe_version_id,
        recipe_name=recipe_name,
        ingredient_id=task.ingredient_id,
        ingredient_name=ingredient_name,
        amount=task.amount,
        unit=task.unit,
        completed_by_user_id=task.completed_by_user_id,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _preparation_error(exc: PreparationError) -> DomainError:
    return DomainError("conflict", "Preparation task conflict", str(exc), 409)


def _find_receipt(
    session: Session, membership: HouseholdMember, operation: str, key: str
) -> PreparationOperation | None:
    return session.scalar(
        select(PreparationOperation).where(
            PreparationOperation.household_id == membership.household_id,
            PreparationOperation.operation == operation,
            PreparationOperation.idempotency_key == key,
        )
    )


def _check_receipt(receipt: PreparationOperation | None, fingerprint: str) -> dict[str, Any] | None:
    if receipt is None:
        return None
    if receipt.request_hash != fingerprint:
        raise DomainError(
            "conflict",
            "Idempotency key conflict",
            "The key was already used for a different preparation operation.",
            409,
        )
    return receipt.result_payload


def _store_receipt(
    session: Session,
    membership: HouseholdMember,
    operation: str,
    key: str | None,
    fingerprint: str,
    payload: dict[str, Any],
) -> None:
    if key is None:
        return
    session.add(
        PreparationOperation(
            household_id=membership.household_id,
            operation=operation,
            idempotency_key=key,
            request_hash=fingerprint,
            result_payload=payload,
        )
    )


def _commit_or_replay(
    session: Session,
    membership: HouseholdMember,
    operation: str,
    idempotency_key: str | None,
    fingerprint: str,
    conflict_detail: str,
) -> dict[str, Any] | None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if idempotency_key is not None:
            receipt = _find_receipt(session, membership, operation, idempotency_key)
            if receipt is not None:
                return _check_receipt(receipt, fingerprint)
        raise DomainError("conflict", "Preparation task conflict", conflict_detail, 409) from exc
    return None


def _task_row(
    session: Session, membership: HouseholdMember, task: PreparationTask
) -> PreparationTaskResponse:
    entry = (
        session.get(MealPlanEntry, task.meal_plan_entry_id)
        if task.meal_plan_entry_id is not None
        else None
    )
    recipe_name: str | None = None
    if task.recipe_version_id is not None:
        recipe_name = session.scalar(
            select(Recipe.name)
            .join(RecipeVersion, RecipeVersion.recipe_id == Recipe.id)
            .where(RecipeVersion.id == task.recipe_version_id)
        )
    ingredient_name: str | None = None
    if task.ingredient_id is not None:
        ingredient_name = session.scalar(
            select(Ingredient.name).where(Ingredient.id == task.ingredient_id)
        )
    return task_response(task, entry, recipe_name, ingredient_name)


def _task_payload(
    session: Session, membership: HouseholdMember, task: PreparationTask
) -> dict[str, Any]:
    return _task_row(session, membership, task).model_dump(mode="json")


def list_tasks(
    session: Session,
    membership: HouseholdMember,
    status: PreparationTaskStatus | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[PreparationTaskResponse]:
    if from_dt is not None and to_dt is not None and from_dt > to_dt:
        raise DomainError(
            "validation_error",
            "Invalid window",
            "The from timestamp must not be after the to timestamp.",
            422,
        )
    statement = (
        select(PreparationTask)
        .where(PreparationTask.household_id == membership.household_id)
        .order_by(PreparationTask.due_at, PreparationTask.id)
    )
    if status is not None:
        statement = statement.where(PreparationTask.status == status)
    if from_dt is not None:
        statement = statement.where(PreparationTask.due_at >= from_dt)
    if to_dt is not None:
        statement = statement.where(PreparationTask.due_at <= to_dt)
    return [_task_row(session, membership, task) for task in session.scalars(statement)]


def _get_task(
    session: Session, membership: HouseholdMember, task_id: UUID, lock: bool = False
) -> PreparationTask:
    statement = select(PreparationTask).where(
        PreparationTask.id == task_id,
        PreparationTask.household_id == membership.household_id,
    )
    if lock:
        statement = statement.with_for_update()
    task = session.scalar(statement)
    if task is None:
        raise DomainError(
            "not_found",
            "Preparation task not found",
            "The preparation task could not be found.",
            404,
        )
    return task


def _tenant_ingredient(
    session: Session, membership: HouseholdMember, ingredient_id: UUID
) -> Ingredient:
    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise DomainError(
            "not_found", "Ingredient not found", "The ingredient could not be found.", 404
        )
    if ingredient.household_id != membership.household_id:
        raise DomainError(
            "forbidden",
            "Permission denied",
            "The ingredient is not available to this household.",
            403,
        )
    return ingredient


def create_manual_task(
    session: Session,
    membership: HouseholdMember,
    payload: PreparationTaskCreate,
    idempotency_key: str | None,
) -> PreparationMutationResult:
    operation = "preparation_task_create"
    fingerprint = operation_fingerprint(
        operation,
        {
            "title": payload.title,
            "instruction": payload.instruction,
            "due_at": payload.due_at.isoformat(),
            "ingredient_id": str(payload.ingredient_id) if payload.ingredient_id else None,
            "amount": str(payload.amount) if payload.amount is not None else None,
            "unit": payload.unit,
        },
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return PreparationMutationResult(replay)
    try:
        title, amount, unit = validate_manual_task(payload.title, payload.amount, payload.unit)
    except PreparationError as exc:
        raise DomainError("validation_error", "Invalid task", str(exc), 422) from exc
    if payload.ingredient_id is not None:
        ingredient = _tenant_ingredient(session, membership, payload.ingredient_id)
        if unit is not None:
            try:
                validate_unit_for_dimension(ingredient.dimension, unit)
            except ValueError as exc:
                raise DomainError("validation_error", "Invalid unit", str(exc), 422) from exc
    task = PreparationTask(
        household_id=membership.household_id,
        origin=PreparationTaskOrigin.MANUAL,
        task_type=PreparationTaskType.MANUAL,
        title=title,
        instruction=payload.instruction,
        due_at=payload.due_at.astimezone(UTC),
        status=PreparationTaskStatus.PENDING,
        version=1,
        ingredient_id=payload.ingredient_id,
        amount=amount,
        unit=unit,
        created_by_user_id=membership.user_id,
    )
    try:
        session.add(task)
        session.flush()
        result = _task_payload(session, membership, task)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The task conflicts with the current preparation state.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Preparation task conflict",
            "The task conflicts with the current preparation state.",
            409,
        ) from exc
    if replay is not None:
        return PreparationMutationResult(replay)
    return PreparationMutationResult(result)


def transition_task(
    session: Session,
    membership: HouseholdMember,
    task_id: UUID,
    action: PreparationTaskAction,
    expected_version: int,
    idempotency_key: str | None,
) -> PreparationMutationResult:
    operation = f"preparation_task_{action.value}"
    fingerprint = operation_fingerprint(
        operation, {"task_id": str(task_id), "expected_version": expected_version}
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return PreparationMutationResult(replay)
    task = _get_task(session, membership, task_id, lock=True)
    try:
        task.version = assert_version(expected_version, task.version)
        task.status = apply_task_transition(task.status, action)
    except PreparationError as exc:
        raise _preparation_error(exc) from exc
    if task.status == PreparationTaskStatus.COMPLETED:
        task.completed_by_user_id = membership.user_id
        task.completed_at = datetime.now(UTC)
    if task.status == PreparationTaskStatus.COMPLETED:
        event_kind = DomainEventKind.PREPARATION_COMPLETED
    elif task.status == PreparationTaskStatus.CANCELLED:
        event_kind = DomainEventKind.PREPARATION_CANCELLED
    else:
        event_kind = None
    if event_kind is not None:
        record_event(
            session,
            household_id=membership.household_id,
            kind=event_kind,
            actor_user_id=membership.user_id,
            aggregate_type="preparation_task",
            aggregate_id=task.id,
            payload={"task_type": task.task_type.value},
        )
    try:
        session.flush()
        result = _task_payload(session, membership, task)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The task changed since it was loaded.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Preparation task conflict",
            "The task changed since it was loaded.",
            409,
        ) from exc
    if replay is not None:
        return PreparationMutationResult(replay)
    return PreparationMutationResult(result)


def _get_draft_version(
    session: Session, membership: HouseholdMember, recipe_id: UUID, version_id: UUID
) -> tuple[Recipe, RecipeVersion]:
    recipe = session.get(Recipe, recipe_id)
    if recipe is None or recipe.household_id != membership.household_id:
        raise DomainError("not_found", "Recipe not found", "The recipe could not be found.", 404)
    version = session.scalar(
        select(RecipeVersion).where(
            RecipeVersion.id == version_id,
            RecipeVersion.recipe_id == recipe.id,
        )
    )
    if version is None:
        raise DomainError(
            "not_found",
            "Recipe version not found",
            "The recipe version could not be found.",
            404,
        )
    if version.state != RecipeVersionState.DRAFT:
        raise DomainError(
            "validation_error",
            "Recipe version is not a draft",
            "Preparation rules can only change on draft versions.",
            422,
        )
    return recipe, version


def add_rule(
    session: Session,
    membership: HouseholdMember,
    recipe_id: UUID,
    version_id: UUID,
    payload: PreparationRuleCreate,
) -> PreparationRuleResponse:
    _recipe, version = _get_draft_version(session, membership, recipe_id, version_id)
    ingredient_name: str | None = None
    if payload.ingredient_id is not None:
        ingredient_name = _tenant_ingredient(session, membership, payload.ingredient_id).name
    rule = RecipePreparationRule(
        recipe_version_id=version.id,
        rule_type=payload.rule_type,
        ingredient_id=payload.ingredient_id,
        lead_minutes=payload.lead_minutes,
        instruction=payload.instruction,
    )
    try:
        session.add(rule)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Preparation rule conflict",
            "The rule conflicts with the current version state.",
            409,
        ) from exc
    session.refresh(rule)
    return PreparationRuleResponse(
        id=rule.id,
        recipe_version_id=rule.recipe_version_id,
        rule_type=rule.rule_type,
        ingredient_id=rule.ingredient_id,
        ingredient_name=ingredient_name,
        lead_minutes=rule.lead_minutes,
        instruction=rule.instruction,
    )


def delete_rule(
    session: Session,
    membership: HouseholdMember,
    recipe_id: UUID,
    version_id: UUID,
    rule_id: UUID,
) -> None:
    _recipe, version = _get_draft_version(session, membership, recipe_id, version_id)
    rule = session.scalar(
        select(RecipePreparationRule).where(
            RecipePreparationRule.id == rule_id,
            RecipePreparationRule.recipe_version_id == version.id,
        )
    )
    if rule is None:
        raise DomainError(
            "not_found",
            "Preparation rule not found",
            "The preparation rule could not be found.",
            404,
        )
    session.delete(rule)
    session.commit()


_RULE_LABELS: dict[PreparationRuleType, str] = {
    PreparationRuleType.DEFROST: "Defrost",
    PreparationRuleType.SOAK: "Soak",
    PreparationRuleType.MARINATE: "Marinate",
    PreparationRuleType.PREPARE_AHEAD: "Prepare ahead",
}


def _derived_title(
    rule: RecipePreparationRule,
    ingredient_name: str | None,
    recipe_name: str | None,
) -> str:
    label = _RULE_LABELS.get(rule.rule_type, rule.rule_type.value.replace("_", " ").title())
    parts = [label]
    if ingredient_name:
        parts.append(ingredient_name)
    title = " ".join(parts)
    if recipe_name:
        title = f"{title} — {recipe_name}"
    return title[:200]


def reconcile_derived_tasks(session: Session, membership: HouseholdMember, plan: MealPlan) -> None:
    entries = list(
        session.scalars(
            select(MealPlanEntry).where(
                MealPlanEntry.meal_plan_id == plan.id,
                MealPlanEntry.household_id == membership.household_id,
            )
        )
    )
    household = session.get(Household, membership.household_id)
    timezone_name = household.timezone if household is not None else None

    desired: dict[str, tuple[MealPlanEntry, RecipePreparationRule]] = {}
    for entry in entries:
        rules = session.scalars(
            select(RecipePreparationRule).where(
                RecipePreparationRule.recipe_version_id == entry.recipe_version_id
            )
        )
        for rule in rules:
            desired[derived_fingerprint(entry.id, rule.id)] = (entry, rule)

    entry_ids = [entry.id for entry in entries]
    existing: list[PreparationTask] = []
    if entry_ids:
        existing = list(
            session.scalars(
                select(PreparationTask)
                .join(
                    MealPlanEntry,
                    MealPlanEntry.id == PreparationTask.meal_plan_entry_id,
                )
                .where(
                    MealPlanEntry.meal_plan_id == plan.id,
                    PreparationTask.household_id == membership.household_id,
                    PreparationTask.origin == PreparationTaskOrigin.DERIVED,
                )
                .with_for_update(of=PreparationTask)
            )
        )
    existing_fingerprints = {task.fingerprint for task in existing}
    for task in existing:
        if task.fingerprint not in desired and task.status == PreparationTaskStatus.PENDING:
            task.status = PreparationTaskStatus.CANCELLED
            task.version += 1

    for fingerprint, (entry, rule) in desired.items():
        if fingerprint in existing_fingerprints:
            continue
        ingredient_name: str | None = None
        if rule.ingredient_id is not None:
            ingredient_name = session.scalar(
                select(Ingredient.name).where(Ingredient.id == rule.ingredient_id)
            )
        recipe_name = session.scalar(
            select(Recipe.name)
            .join(RecipeVersion, RecipeVersion.recipe_id == Recipe.id)
            .where(RecipeVersion.id == entry.recipe_version_id)
        )
        session.add(
            PreparationTask(
                household_id=membership.household_id,
                origin=PreparationTaskOrigin.DERIVED,
                task_type=rule_type_to_task_type(rule.rule_type),
                title=_derived_title(rule, ingredient_name, recipe_name),
                instruction=rule.instruction,
                due_at=compute_due_at(
                    entry.planned_date,
                    entry.meal_type,
                    rule.lead_minutes,
                    timezone_name,
                ),
                status=PreparationTaskStatus.PENDING,
                version=1,
                meal_plan_entry_id=entry.id,
                recipe_version_id=entry.recipe_version_id,
                ingredient_id=rule.ingredient_id,
                fingerprint=fingerprint,
                created_by_user_id=membership.user_id,
            )
        )
    session.flush()
