from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanEntryUpdate,
    MealPlanTransition,
)
from uribap_api.domain.planning.policies import (
    MealPlanAction,
    MealPlanningError,
    MealPlanState,
    apply_transition,
    assert_version,
    can_edit_entries,
    validate_planned_date,
)
from uribap_api.domain.recipes.policies import RecipeVersionState
from uribap_api.domain.shared.errors import DomainError
from uribap_api.domain.shared.fingerprint import operation_fingerprint
from uribap_api.infrastructure.persistence.household_models import (
    HouseholdMember,
    MembershipStatus,
)
from uribap_api.infrastructure.persistence.planning_models import (
    MealPlan,
    MealPlanEntry,
    MealPlanOperation,
    MealPlanStateEvent,
)
from uribap_api.infrastructure.persistence.recipe_models import Recipe, RecipeVersion


@dataclass(frozen=True)
class PlanMutationResult:
    plan: MealPlan
    payload: dict[str, Any]


def _get_plan(
    session: Session, membership: HouseholdMember, plan_id: UUID, lock: bool = False
) -> MealPlan:
    statement = select(MealPlan).where(
        MealPlan.id == plan_id,
        MealPlan.household_id == membership.household_id,
    )
    if lock:
        statement = statement.with_for_update()
    plan = session.scalar(statement)
    if plan is None:
        raise DomainError(
            "not_found", "Meal plan not found", "The meal plan could not be found.", 404
        )
    return plan


def _active_member_count(session: Session, membership: HouseholdMember) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(HouseholdMember)
            .where(
                HouseholdMember.household_id == membership.household_id,
                HouseholdMember.status == MembershipStatus.ACTIVE,
            )
        )
        or 0
    )


def _planning_error(exc: MealPlanningError) -> DomainError:
    return DomainError("conflict", "Meal plan conflict", str(exc), 409)


def _find_receipt(
    session: Session, membership: HouseholdMember, operation: str, key: str
) -> MealPlanOperation | None:
    return session.scalar(
        select(MealPlanOperation).where(
            MealPlanOperation.household_id == membership.household_id,
            MealPlanOperation.operation == operation,
            MealPlanOperation.idempotency_key == key,
        )
    )


def _check_receipt(receipt: MealPlanOperation | None, fingerprint: str) -> dict[str, Any] | None:
    if receipt is None:
        return None
    if receipt.request_hash != fingerprint:
        raise DomainError(
            "conflict",
            "Idempotency key conflict",
            "The key was already used for a different meal plan operation.",
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
        MealPlanOperation(
            household_id=membership.household_id,
            operation=operation,
            idempotency_key=key,
            request_hash=fingerprint,
            result_payload=payload,
        )
    )


def _locked_plan(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    expected_version: int,
) -> MealPlan:
    plan = _get_plan(session, membership, plan_id, lock=True)
    try:
        plan.version = assert_version(expected_version, plan.version)
    except MealPlanningError as exc:
        raise _planning_error(exc) from exc
    return plan


def _assert_editable(plan: MealPlan) -> None:
    if not can_edit_entries(plan.state):
        raise DomainError(
            "conflict",
            "Meal plan is not editable",
            "Entries can only change while the plan is a draft.",
            409,
        )


def _assert_published_version(
    session: Session, membership: HouseholdMember, recipe_version_id: UUID
) -> None:
    version = session.get(RecipeVersion, recipe_version_id)
    if version is None:
        raise DomainError(
            "not_found", "Recipe version not found", "The recipe version could not be found.", 404
        )
    recipe = session.get(Recipe, version.recipe_id)
    if recipe is None or recipe.household_id != membership.household_id:
        raise DomainError(
            "forbidden",
            "Permission denied",
            "The recipe version is not available to this household.",
            403,
        )
    if version.state != RecipeVersionState.PUBLISHED:
        raise DomainError(
            "validation_error",
            "Recipe version not published",
            "Only published recipe versions can be planned.",
            422,
        )


def create_plan(
    session: Session,
    membership: HouseholdMember,
    payload: MealPlanCreate,
    idempotency_key: str | None,
) -> MealPlan:
    operation = "meal_plan_create"
    fingerprint = operation_fingerprint(
        operation, {"week_start_date": str(payload.week_start_date)}
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return _get_plan(session, membership, UUID(replay["id"]))
    plan = MealPlan(
        household_id=membership.household_id,
        week_start_date=payload.week_start_date,
        state=MealPlanState.DRAFT,
        version=1,
        created_by_user_id=membership.user_id,
    )
    session.add(plan)
    session.flush()
    session.add(
        MealPlanStateEvent(
            household_id=membership.household_id,
            meal_plan_id=plan.id,
            from_state=None,
            to_state=MealPlanState.DRAFT,
            actor_user_id=membership.user_id,
        )
    )
    _store_receipt(
        session, membership, operation, idempotency_key, fingerprint, {"id": str(plan.id)}
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal plan conflict",
            "A plan already exists for this household and week.",
            409,
        ) from exc
    session.refresh(plan)
    return plan


def get_plan(session: Session, membership: HouseholdMember, plan_id: UUID) -> MealPlan:
    return _get_plan(session, membership, plan_id)


def get_current_plan(session: Session, membership: HouseholdMember, week_start) -> MealPlan:
    plan = session.scalar(
        select(MealPlan).where(
            MealPlan.household_id == membership.household_id,
            MealPlan.week_start_date == week_start,
            MealPlan.state != MealPlanState.ARCHIVED,
        )
    )
    if plan is None:
        raise DomainError(
            "not_found", "Meal plan not found", "No active plan exists for that week.", 404
        )
    return plan


def list_entries(
    session: Session, membership: HouseholdMember, plan_id: UUID
) -> list[MealPlanEntry]:
    _get_plan(session, membership, plan_id)
    return list(
        session.scalars(
            select(MealPlanEntry)
            .where(
                MealPlanEntry.household_id == membership.household_id,
                MealPlanEntry.meal_plan_id == plan_id,
            )
            .order_by(MealPlanEntry.planned_date, MealPlanEntry.position, MealPlanEntry.id)
        )
    )


def list_events(
    session: Session, membership: HouseholdMember, plan_id: UUID
) -> list[MealPlanStateEvent]:
    _get_plan(session, membership, plan_id)
    return list(
        session.scalars(
            select(MealPlanStateEvent)
            .where(
                MealPlanStateEvent.household_id == membership.household_id,
                MealPlanStateEvent.meal_plan_id == plan_id,
            )
            .order_by(MealPlanStateEvent.created_at, MealPlanStateEvent.id)
        )
    )


def _get_entry(
    session: Session, membership: HouseholdMember, plan: MealPlan, entry_id: UUID
) -> MealPlanEntry:
    entry = session.scalar(
        select(MealPlanEntry).where(
            MealPlanEntry.id == entry_id,
            MealPlanEntry.meal_plan_id == plan.id,
            MealPlanEntry.household_id == membership.household_id,
        )
    )
    if entry is None:
        raise DomainError(
            "not_found", "Meal plan entry not found", "The plan entry could not be found.", 404
        )
    return entry


def add_entry(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    payload: MealPlanEntryCreate,
    idempotency_key: str | None,
) -> tuple[MealPlan, MealPlanEntry]:
    operation = "meal_plan_entry_create"
    fingerprint = operation_fingerprint(
        operation,
        {
            "plan_id": str(plan_id),
            "planned_date": str(payload.planned_date),
            "meal_type": payload.meal_type.value,
            "recipe_version_id": str(payload.recipe_version_id),
            "servings": payload.servings,
            "position": payload.position,
            "notes": payload.notes,
            "expected_version": payload.expected_version,
        },
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            plan = _get_plan(session, membership, plan_id)
            return plan, _get_entry(session, membership, plan, UUID(replay["entry_id"]))
    plan = _locked_plan(session, membership, plan_id, payload.expected_version)
    _assert_editable(plan)
    try:
        validate_planned_date(payload.planned_date, plan.week_start_date)
    except MealPlanningError as exc:
        raise DomainError("validation_error", "Invalid planned date", str(exc), 422) from exc
    _assert_published_version(session, membership, payload.recipe_version_id)
    entry = MealPlanEntry(
        household_id=membership.household_id,
        meal_plan_id=plan.id,
        planned_date=payload.planned_date,
        meal_type=payload.meal_type,
        recipe_version_id=payload.recipe_version_id,
        servings=payload.servings,
        position=payload.position,
        notes=payload.notes,
        added_by_user_id=membership.user_id,
    )
    session.add(entry)
    session.flush()
    _store_receipt(
        session,
        membership,
        operation,
        idempotency_key,
        fingerprint,
        {"entry_id": str(entry.id)},
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal plan entry conflict",
            "The entry conflicts with the current plan state.",
            409,
        ) from exc
    session.refresh(plan)
    session.refresh(entry)
    return plan, entry


def update_entry(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    entry_id: UUID,
    payload: MealPlanEntryUpdate,
    idempotency_key: str | None,
) -> tuple[MealPlan, MealPlanEntry]:
    operation = "meal_plan_entry_update"
    fingerprint = operation_fingerprint(
        operation,
        {
            "plan_id": str(plan_id),
            "entry_id": str(entry_id),
            "planned_date": str(payload.planned_date) if payload.planned_date else None,
            "meal_type": payload.meal_type.value if payload.meal_type else None,
            "servings": payload.servings,
            "position": payload.position,
            "notes": payload.notes,
            "expected_version": payload.expected_version,
        },
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            plan = _get_plan(session, membership, plan_id)
            return plan, _get_entry(session, membership, plan, entry_id)
    plan = _locked_plan(session, membership, plan_id, payload.expected_version)
    _assert_editable(plan)
    entry = _get_entry(session, membership, plan, entry_id)
    if payload.planned_date is not None:
        try:
            validate_planned_date(payload.planned_date, plan.week_start_date)
        except MealPlanningError as exc:
            raise DomainError("validation_error", "Invalid planned date", str(exc), 422) from exc
        entry.planned_date = payload.planned_date
    if payload.meal_type is not None:
        entry.meal_type = payload.meal_type
    if payload.servings is not None:
        entry.servings = payload.servings
    if payload.position is not None:
        entry.position = payload.position
    if payload.notes is not None:
        entry.notes = payload.notes
    _store_receipt(
        session, membership, operation, idempotency_key, fingerprint, {"entry_id": str(entry.id)}
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal plan entry conflict",
            "The entry conflicts with the current plan state.",
            409,
        ) from exc
    session.refresh(plan)
    session.refresh(entry)
    return plan, entry


def delete_entry(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    entry_id: UUID,
    expected_version: int,
    idempotency_key: str | None,
) -> MealPlan:
    operation = "meal_plan_entry_delete"
    fingerprint = operation_fingerprint(
        operation,
        {"plan_id": str(plan_id), "entry_id": str(entry_id), "expected_version": expected_version},
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return _get_plan(session, membership, plan_id)
    plan = _locked_plan(session, membership, plan_id, expected_version)
    _assert_editable(plan)
    entry = _get_entry(session, membership, plan, entry_id)
    session.delete(entry)
    _store_receipt(
        session, membership, operation, idempotency_key, fingerprint, {"entry_id": str(entry_id)}
    )
    session.commit()
    session.refresh(plan)
    return plan


def transition_plan(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    action: MealPlanAction,
    payload: MealPlanTransition,
    idempotency_key: str | None,
) -> MealPlan:
    operation = f"meal_plan_{action.value}"
    fingerprint = operation_fingerprint(
        operation,
        {
            "plan_id": str(plan_id),
            "note": payload.note,
            "expected_version": payload.expected_version,
        },
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return _get_plan(session, membership, plan_id)
    plan = _locked_plan(session, membership, plan_id, payload.expected_version)
    proposed_by = session.scalar(
        select(MealPlanStateEvent.actor_user_id)
        .where(
            MealPlanStateEvent.meal_plan_id == plan.id,
            MealPlanStateEvent.to_state == MealPlanState.PROPOSED,
        )
        .order_by(MealPlanStateEvent.created_at.desc(), MealPlanStateEvent.id.desc())
        .limit(1)
    )
    try:
        target = apply_transition(
            plan.state,
            action,
            actor_id=membership.user_id,
            proposed_by=proposed_by,
            active_member_count=_active_member_count(session, membership),
            note=payload.note,
        )
    except MealPlanningError as exc:
        raise _planning_error(exc) from exc
    previous = plan.state
    plan.state = target
    session.add(
        MealPlanStateEvent(
            household_id=membership.household_id,
            meal_plan_id=plan.id,
            from_state=previous,
            to_state=target,
            actor_user_id=membership.user_id,
            note=payload.note,
        )
    )
    _store_receipt(
        session, membership, operation, idempotency_key, fingerprint, {"state": target.value}
    )
    session.commit()
    session.refresh(plan)
    return plan
