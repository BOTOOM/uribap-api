from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanEntryResponse,
    MealPlanEntryUpdate,
    MealPlanResponse,
    MealPlanStateEventResponse,
    MealPlanTransition,
)
from uribap_api.domain.planning.policies import (
    MealPlanAction,
    MealPlanningError,
    MealPlanState,
    PlanEntryDraft,
    apply_transition,
    assert_version,
    can_edit_entries,
    validate_planned_date,
    validate_servings,
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
    payload: dict[str, Any]


def entry_response(entry: MealPlanEntry) -> MealPlanEntryResponse:
    return MealPlanEntryResponse(
        id=entry.id,
        meal_plan_id=entry.meal_plan_id,
        planned_date=entry.planned_date,
        meal_type=entry.meal_type,
        recipe_version_id=entry.recipe_version_id,
        servings=entry.servings,
        position=entry.position,
        notes=entry.notes,
        added_by_user_id=entry.added_by_user_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def plan_response(
    session: Session, membership: HouseholdMember, plan: MealPlan
) -> MealPlanResponse:
    return MealPlanResponse(
        id=plan.id,
        household_id=plan.household_id,
        week_start_date=plan.week_start_date,
        state=plan.state,
        version=plan.version,
        entries=[entry_response(entry) for entry in list_entries(session, membership, plan.id)],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def event_response(event: MealPlanStateEvent) -> MealPlanStateEventResponse:
    return MealPlanStateEventResponse(
        id=event.id,
        meal_plan_id=event.meal_plan_id,
        from_state=event.from_state,
        to_state=event.to_state,
        actor_user_id=event.actor_user_id,
        note=event.note,
        created_at=event.created_at,
    )


def _plan_payload(session: Session, membership: HouseholdMember, plan: MealPlan) -> dict[str, Any]:
    return plan_response(session, membership, plan).model_dump(mode="json")


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
        raise DomainError("conflict", "Meal plan conflict", conflict_detail, 409) from exc
    return None


def _locked_plan(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    expected_version: int,
) -> MealPlan:
    plan = _get_plan(session, membership, plan_id, lock=True)
    try:
        assert_version(expected_version, plan.version)
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
) -> PlanMutationResult:
    operation = "meal_plan_create"
    fingerprint = operation_fingerprint(
        operation, {"week_start_date": str(payload.week_start_date)}
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return PlanMutationResult(replay)
    plan = MealPlan(
        household_id=membership.household_id,
        week_start_date=payload.week_start_date,
        state=MealPlanState.DRAFT,
        version=1,
        created_by_user_id=membership.user_id,
    )
    try:
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
        result = _plan_payload(session, membership, plan)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "A plan already exists for this household and week.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal plan conflict",
            "A plan already exists for this household and week.",
            409,
        ) from exc
    if replay is not None:
        return PlanMutationResult(replay)
    return PlanMutationResult(result)


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
) -> PlanMutationResult:
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
            return PlanMutationResult(replay)
    plan = _locked_plan(session, membership, plan_id, payload.expected_version)
    _assert_editable(plan)
    try:
        draft = PlanEntryDraft(
            planned_date=payload.planned_date,
            meal_type=payload.meal_type,
            recipe_version_id=payload.recipe_version_id,
            servings=payload.servings,
            position=payload.position,
            notes=payload.notes,
        )
        validate_planned_date(draft.planned_date, plan.week_start_date)
    except MealPlanningError as exc:
        raise DomainError("validation_error", "Invalid plan entry", str(exc), 422) from exc
    _assert_published_version(session, membership, draft.recipe_version_id)
    entry = MealPlanEntry(
        household_id=membership.household_id,
        meal_plan_id=plan.id,
        planned_date=draft.planned_date,
        meal_type=draft.meal_type,
        recipe_version_id=draft.recipe_version_id,
        servings=draft.servings,
        position=draft.position,
        notes=draft.notes,
        added_by_user_id=membership.user_id,
    )
    try:
        plan.version += 1
        session.add(entry)
        session.flush()
        result = _plan_payload(session, membership, plan)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The entry conflicts with the current plan state.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal plan entry conflict",
            "The entry conflicts with the current plan state.",
            409,
        ) from exc
    if replay is not None:
        return PlanMutationResult(replay)
    return PlanMutationResult(result)


def update_entry(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    entry_id: UUID,
    payload: MealPlanEntryUpdate,
    idempotency_key: str | None,
) -> PlanMutationResult:
    operation = "meal_plan_entry_update"
    fingerprint = operation_fingerprint(
        operation,
        {
            "plan_id": str(plan_id),
            "entry_id": str(entry_id),
            "planned_date": str(payload.planned_date) if payload.planned_date else None,
            "meal_type": payload.meal_type.value if payload.meal_type else None,
            "recipe_version_id": str(payload.recipe_version_id)
            if payload.recipe_version_id
            else None,
            "servings": payload.servings,
            "position": payload.position,
            "notes": payload.notes if "notes" in payload.model_fields_set else "<unset>",
            "expected_version": payload.expected_version,
        },
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return PlanMutationResult(replay)
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
    if payload.recipe_version_id is not None:
        _assert_published_version(session, membership, payload.recipe_version_id)
        entry.recipe_version_id = payload.recipe_version_id
    if payload.servings is not None:
        try:
            entry.servings = validate_servings(payload.servings)
        except MealPlanningError as exc:
            raise DomainError("validation_error", "Invalid servings", str(exc), 422) from exc
    if payload.position is not None:
        entry.position = payload.position
    if "notes" in payload.model_fields_set:
        entry.notes = payload.notes
    try:
        plan.version += 1
        session.flush()
        result = _plan_payload(session, membership, plan)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The entry conflicts with the current plan state.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal plan entry conflict",
            "The entry conflicts with the current plan state.",
            409,
        ) from exc
    if replay is not None:
        return PlanMutationResult(replay)
    return PlanMutationResult(result)


def delete_entry(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    entry_id: UUID,
    expected_version: int,
    idempotency_key: str | None,
) -> PlanMutationResult:
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
            return PlanMutationResult(replay)
    plan = _locked_plan(session, membership, plan_id, expected_version)
    _assert_editable(plan)
    entry = _get_entry(session, membership, plan, entry_id)
    try:
        plan.version += 1
        session.delete(entry)
        session.flush()
        result = _plan_payload(session, membership, plan)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The entry could not be removed from the current plan state.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal plan entry conflict",
            "The entry could not be removed from the current plan state.",
            409,
        ) from exc
    if replay is not None:
        return PlanMutationResult(replay)
    return PlanMutationResult(result)


def transition_plan(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    action: MealPlanAction,
    payload: MealPlanTransition,
    idempotency_key: str | None,
) -> PlanMutationResult:
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
            return PlanMutationResult(replay)
    plan = _locked_plan(session, membership, plan_id, payload.expected_version)
    if (
        action == MealPlanAction.REOPEN
        and plan.state == MealPlanState.APPROVED
        and not payload.note
    ):
        raise DomainError(
            "validation_error",
            "Note required",
            "Reopening an approved plan requires a note.",
            422,
        )
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
    try:
        plan.version += 1
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
        session.flush()
        result = _plan_payload(session, membership, plan)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The transition conflicts with the current plan state.",
        )
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal plan conflict",
            "The transition conflicts with the current plan state.",
            409,
        ) from exc
    if replay is not None:
        return PlanMutationResult(replay)
    return PlanMutationResult(result)
