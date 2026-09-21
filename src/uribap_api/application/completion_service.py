from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.completion_schemas import (
    MealCompletionCreate,
    MealCompletionLineResponse,
    MealCompletionResponse,
)
from uribap_api.domain.completion.policies import (
    ActualLineInput,
    ConsumptionLine,
    MealCompletionAction,
    MealCompletionError,
    MealCompletionState,
    RecipeIngredientInput,
    StockLot,
    apply_actual_amounts,
    apply_completion_transition,
    assert_version,
    fefo_allocate,
    planned_lines,
)
from uribap_api.domain.inventory.ledger import (
    InventoryLedgerError,
    InventoryMovementType,
    LedgerBalance,
    quantize_amount,
)
from uribap_api.domain.planning.policies import MealPlanState
from uribap_api.domain.shared.errors import DomainError
from uribap_api.domain.shared.fingerprint import operation_fingerprint
from uribap_api.infrastructure.persistence.completion_models import (
    CompletionOperation,
    MealCompletion,
    MealCompletionLine,
)
from uribap_api.infrastructure.persistence.household_models import HouseholdMember
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import (
    InventoryLot,
    InventoryMovement,
)
from uribap_api.infrastructure.persistence.planning_models import MealPlan, MealPlanEntry
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeVersion,
    RecipeVersionIngredient,
)

COMPLETION_SOURCE_TYPE = "meal_completion_line"


@dataclass(frozen=True)
class CompletionMutationResult:
    payload: dict[str, Any]


def _completion_error(exc: MealCompletionError) -> DomainError:
    return DomainError("conflict", "Meal completion conflict", str(exc), 409)


def _validation_error(exc: MealCompletionError) -> DomainError:
    return DomainError("validation_error", "Invalid completion", str(exc), 422)


def _find_receipt(
    session: Session, membership: HouseholdMember, operation: str, key: str
) -> CompletionOperation | None:
    return session.scalar(
        select(CompletionOperation).where(
            CompletionOperation.household_id == membership.household_id,
            CompletionOperation.operation == operation,
            CompletionOperation.idempotency_key == key,
        )
    )


def _check_receipt(receipt: CompletionOperation | None, fingerprint: str) -> dict[str, Any] | None:
    if receipt is None:
        return None
    if receipt.request_hash != fingerprint:
        raise DomainError(
            "conflict",
            "Idempotency key conflict",
            "The key was already used for a different completion operation.",
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
        CompletionOperation(
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
        raise DomainError("conflict", "Meal completion conflict", conflict_detail, 409) from exc
    return None


def _completion_row(session: Session, completion: MealCompletion) -> MealCompletionResponse:
    entry = session.get(MealPlanEntry, completion.meal_plan_entry_id)
    recipe_name: str | None = None
    recipe_version_id: UUID | None = entry.recipe_version_id if entry else None
    if recipe_version_id is not None:
        recipe_name = session.scalar(
            select(Recipe.name)
            .join(RecipeVersion, RecipeVersion.recipe_id == Recipe.id)
            .where(RecipeVersion.id == recipe_version_id)
        )
    lines = list(
        session.scalars(
            select(MealCompletionLine)
            .where(MealCompletionLine.meal_completion_id == completion.id)
            .order_by(MealCompletionLine.position, MealCompletionLine.id)
        )
    )
    ingredient_ids = [line.ingredient_id for line in lines]
    names: dict[UUID, str] = {}
    if ingredient_ids:
        rows = session.execute(
            select(Ingredient.id, Ingredient.name).where(Ingredient.id.in_(ingredient_ids))
        ).all()
        names = {row[0]: row[1] for row in rows}
    return MealCompletionResponse(
        id=completion.id,
        state=completion.state,
        version=completion.version,
        meal_plan_entry_id=completion.meal_plan_entry_id,
        planned_date=entry.planned_date if entry else None,
        meal_type=entry.meal_type if entry else None,
        recipe_version_id=recipe_version_id,
        recipe_name=recipe_name,
        lines=[
            MealCompletionLineResponse(
                id=line.id,
                ingredient_id=line.ingredient_id,
                ingredient_name=names.get(line.ingredient_id),
                planned_amount=line.planned_amount,
                actual_amount=line.actual_amount,
                unit=line.unit,
                optional=line.optional,
                position=line.position,
            )
            for line in lines
        ],
        completed_by_user_id=completion.completed_by_user_id,
        completed_at=completion.completed_at,
        reopened_by_user_id=completion.reopened_by_user_id,
        reopened_at=completion.reopened_at,
        reopen_reason=completion.reopen_reason,
        created_at=completion.created_at,
        updated_at=completion.updated_at,
    )


def _completion_payload(session: Session, completion: MealCompletion) -> dict[str, Any]:
    return _completion_row(session, completion).model_dump(mode="json")


def _get_completion(
    session: Session,
    membership: HouseholdMember,
    completion_id: UUID,
    lock: bool = False,
) -> MealCompletion:
    statement = select(MealCompletion).where(
        MealCompletion.id == completion_id,
        MealCompletion.household_id == membership.household_id,
    )
    if lock:
        statement = statement.with_for_update()
    completion = session.scalar(statement)
    if completion is None:
        raise DomainError(
            "not_found",
            "Meal completion not found",
            "The meal completion could not be found.",
            404,
        )
    return completion


def _locked_lots(
    session: Session, membership: HouseholdMember, line: ConsumptionLine
) -> list[InventoryLot]:
    return list(
        session.scalars(
            select(InventoryLot)
            .where(
                InventoryLot.household_id == membership.household_id,
                InventoryLot.ingredient_id == line.ingredient_id,
                InventoryLot.unit == line.unit,
                InventoryLot.available.is_(True),
                InventoryLot.quantity_on_hand > 0,
            )
            .order_by(InventoryLot.expiration_date.asc().nulls_last(), InventoryLot.id)
            .with_for_update()
        )
    )


def _write_movement(
    session: Session,
    membership: HouseholdMember,
    lot: InventoryLot,
    delta: Decimal,
    movement_type: InventoryMovementType,
    source_id: UUID,
    operation: str,
) -> None:
    try:
        balance = LedgerBalance(Decimal(lot.quantity_on_hand), lot.unit).apply(delta, lot.unit)
    except ValueError as exc:
        raise DomainError("conflict", "Inventory balance conflict", str(exc), 409) from exc
    lot.quantity_on_hand = balance.amount
    session.add(
        InventoryMovement(
            household_id=membership.household_id,
            lot_id=lot.id,
            delta=delta,
            unit=lot.unit,
            movement_type=movement_type,
            actor_user_id=membership.user_id,
            source_type=COMPLETION_SOURCE_TYPE,
            source_id=source_id,
            operation=operation,
            result_quantity_on_hand=balance.amount,
        )
    )


def _deduct_line(
    session: Session,
    membership: HouseholdMember,
    line: ConsumptionLine,
    line_id: UUID,
    operation: str,
) -> None:
    lots = _locked_lots(session, membership, line)
    stock = [
        StockLot(
            lot_id=lot.id,
            quantity_on_hand=Decimal(lot.quantity_on_hand),
            unit=lot.unit,
            expiration_date=lot.expiration_date,
        )
        for lot in lots
    ]
    try:
        allocation = fefo_allocate(stock, line.actual_amount, line.unit, date.today())
    except MealCompletionError as exc:
        raise _completion_error(exc) from exc
    by_id = {lot.id: lot for lot in lots}
    for lot_id, amount in allocation:
        _write_movement(
            session,
            membership,
            by_id[lot_id],
            -amount,
            InventoryMovementType.MEAL_CONSUMPTION,
            line_id,
            operation,
        )


def _reverse_line_consumption(
    session: Session,
    membership: HouseholdMember,
    line_id: UUID,
    operation: str,
) -> None:
    rows = session.execute(
        select(InventoryMovement.lot_id, func.sum(InventoryMovement.delta))
        .where(
            InventoryMovement.household_id == membership.household_id,
            InventoryMovement.source_type == COMPLETION_SOURCE_TYPE,
            InventoryMovement.source_id == line_id,
            InventoryMovement.movement_type.in_(
                [InventoryMovementType.MEAL_CONSUMPTION, InventoryMovementType.REVERSAL]
            ),
        )
        .group_by(InventoryMovement.lot_id)
    ).all()
    pending = [(lot_id, Decimal(net)) for lot_id, net in rows if Decimal(net) < 0]
    if not pending:
        return
    lots = {
        lot.id: lot
        for lot in session.scalars(
            select(InventoryLot)
            .where(InventoryLot.id.in_([lot_id for lot_id, _ in pending]))
            .order_by(InventoryLot.id)
            .with_for_update()
        )
    }
    for lot_id, net in pending:
        lot = lots.get(lot_id)
        if lot is None:
            raise DomainError(
                "conflict",
                "Meal completion conflict",
                "A lot referenced by the completion no longer exists.",
                409,
            )
        _write_movement(
            session,
            membership,
            lot,
            -net,
            InventoryMovementType.REVERSAL,
            line_id,
            operation,
        )


def complete_entry(
    session: Session,
    membership: HouseholdMember,
    plan_id: UUID,
    entry_id: UUID,
    payload: MealCompletionCreate,
    idempotency_key: str | None,
) -> CompletionMutationResult:
    operation = "meal_entry_complete"
    fingerprint = operation_fingerprint(
        operation,
        {
            "plan_id": str(plan_id),
            "entry_id": str(entry_id),
            "lines": [
                {
                    "ingredient_id": str(line.ingredient_id),
                    "actual_amount": str(line.actual_amount),
                    "unit": line.unit,
                }
                for line in payload.lines
            ]
            if payload.lines
            else None,
        },
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return CompletionMutationResult(replay)

    plan = session.scalar(
        select(MealPlan)
        .where(MealPlan.id == plan_id, MealPlan.household_id == membership.household_id)
        .with_for_update()
    )
    if plan is None:
        raise DomainError(
            "not_found", "Meal plan not found", "The meal plan could not be found.", 404
        )
    if plan.state != MealPlanState.APPROVED:
        raise DomainError(
            "conflict",
            "Meal plan conflict",
            "Only approved meal plans can record completions.",
            409,
        )
    entry = session.scalar(
        select(MealPlanEntry).where(
            MealPlanEntry.id == entry_id,
            MealPlanEntry.meal_plan_id == plan.id,
            MealPlanEntry.household_id == membership.household_id,
        )
    )
    if entry is None:
        raise DomainError(
            "not_found",
            "Meal plan entry not found",
            "The meal plan entry could not be found.",
            404,
        )
    version = session.get(RecipeVersion, entry.recipe_version_id)
    if version is None:
        raise DomainError(
            "conflict",
            "Meal completion conflict",
            "The recipe version for this entry is unavailable.",
            409,
        )
    ingredients = list(
        session.scalars(
            select(RecipeVersionIngredient)
            .where(RecipeVersionIngredient.recipe_version_id == version.id)
            .order_by(RecipeVersionIngredient.position, RecipeVersionIngredient.id)
        )
    )
    try:
        lines = planned_lines(
            [
                RecipeIngredientInput(
                    ingredient_id=row.ingredient_id,
                    amount=Decimal(row.amount),
                    unit=row.unit,
                    optional=row.optional,
                )
                for row in ingredients
            ],
            entry.servings,
            version.base_servings,
        )
        if payload.lines:
            lines = apply_actual_amounts(
                lines,
                [
                    ActualLineInput(
                        ingredient_id=line.ingredient_id,
                        actual_amount=line.actual_amount,
                        unit=line.unit,
                    )
                    for line in payload.lines
                ],
            )
    except MealCompletionError as exc:
        raise _validation_error(exc) from exc

    completion = MealCompletion(
        household_id=membership.household_id,
        meal_plan_entry_id=entry.id,
        state=MealCompletionState.RECORDED,
        version=1,
        completed_by_user_id=membership.user_id,
        completed_at=datetime.now(UTC),
    )
    try:
        session.add(completion)
        session.flush()
        for position, line in enumerate(lines):
            line_row = MealCompletionLine(
                household_id=membership.household_id,
                meal_completion_id=completion.id,
                ingredient_id=line.ingredient_id,
                planned_amount=line.planned_amount,
                actual_amount=line.actual_amount,
                unit=line.unit,
                optional=line.optional,
                position=position,
            )
            session.add(line_row)
            session.flush()
            _deduct_line(session, membership, line, line_row.id, operation)
        result = _completion_payload(session, completion)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The entry already has a recorded completion.",
        )
    except DomainError:
        session.rollback()
        raise
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal completion conflict",
            "The entry already has a recorded completion.",
            409,
        ) from exc
    if replay is not None:
        return CompletionMutationResult(replay)
    return CompletionMutationResult(result)


def list_completions(
    session: Session,
    membership: HouseholdMember,
    entry_id: UUID | None,
    state: MealCompletionState | None,
    from_dt: datetime | None,
    to_dt: datetime | None,
) -> list[MealCompletionResponse]:
    if from_dt is not None and to_dt is not None and from_dt > to_dt:
        raise DomainError(
            "validation_error",
            "Invalid window",
            "The from timestamp must not be after the to timestamp.",
            422,
        )
    statement = (
        select(MealCompletion)
        .where(MealCompletion.household_id == membership.household_id)
        .order_by(MealCompletion.completed_at.desc(), MealCompletion.id)
    )
    if entry_id is not None:
        statement = statement.where(MealCompletion.meal_plan_entry_id == entry_id)
    if state is not None:
        statement = statement.where(MealCompletion.state == state)
    if from_dt is not None:
        statement = statement.where(MealCompletion.completed_at >= from_dt)
    if to_dt is not None:
        statement = statement.where(MealCompletion.completed_at <= to_dt)
    return [_completion_row(session, row) for row in session.scalars(statement)]


def get_completion(
    session: Session, membership: HouseholdMember, completion_id: UUID
) -> MealCompletionResponse:
    completion = _get_completion(session, membership, completion_id)
    return _completion_row(session, completion)


def correct_line(
    session: Session,
    membership: HouseholdMember,
    completion_id: UUID,
    line_id: UUID,
    expected_version: int,
    actual_amount: Decimal,
    unit: str,
    idempotency_key: str | None,
) -> CompletionMutationResult:
    operation = "meal_completion_line_correct"
    fingerprint = operation_fingerprint(
        operation,
        {
            "completion_id": str(completion_id),
            "line_id": str(line_id),
            "expected_version": expected_version,
            "actual_amount": str(actual_amount),
            "unit": unit,
        },
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return CompletionMutationResult(replay)

    completion = _get_completion(session, membership, completion_id, lock=True)
    line = session.scalar(
        select(MealCompletionLine).where(
            MealCompletionLine.id == line_id,
            MealCompletionLine.meal_completion_id == completion.id,
            MealCompletionLine.household_id == membership.household_id,
        )
    )
    if line is None:
        raise DomainError(
            "not_found",
            "Completion line not found",
            "The completion line could not be found.",
            404,
        )
    try:
        completion.version = assert_version(expected_version, completion.version)
        apply_completion_transition(completion.state, MealCompletionAction.CORRECT)
    except MealCompletionError as exc:
        raise _completion_error(exc) from exc
    if unit != line.unit:
        raise DomainError(
            "validation_error",
            "Invalid unit",
            "The corrected amount must keep the line unit.",
            422,
        )
    try:
        corrected_amount = quantize_amount(actual_amount, allow_zero=False)
    except InventoryLedgerError as exc:
        raise DomainError("validation_error", "Invalid amount", str(exc), 422) from exc
    corrected = ConsumptionLine(
        ingredient_id=line.ingredient_id,
        planned_amount=Decimal(line.planned_amount),
        actual_amount=corrected_amount,
        unit=line.unit,
        optional=line.optional,
    )

    try:
        _reverse_line_consumption(session, membership, line.id, operation)
        session.flush()
        _deduct_line(session, membership, corrected, line.id, operation)
        line.actual_amount = corrected.actual_amount
        session.flush()
        result = _completion_payload(session, completion)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The completion changed since it was loaded.",
        )
    except DomainError:
        session.rollback()
        raise
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal completion conflict",
            "The completion changed since it was loaded.",
            409,
        ) from exc
    if replay is not None:
        return CompletionMutationResult(replay)
    return CompletionMutationResult(result)


def reopen_completion(
    session: Session,
    membership: HouseholdMember,
    completion_id: UUID,
    expected_version: int,
    reason: str | None,
    idempotency_key: str | None,
) -> CompletionMutationResult:
    operation = "meal_completion_reopen"
    fingerprint = operation_fingerprint(
        operation,
        {
            "completion_id": str(completion_id),
            "expected_version": expected_version,
            "reason": reason,
        },
    )
    if idempotency_key:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return CompletionMutationResult(replay)

    completion = _get_completion(session, membership, completion_id, lock=True)
    try:
        completion.version = assert_version(expected_version, completion.version)
        completion.state = apply_completion_transition(
            completion.state, MealCompletionAction.REOPEN
        )
    except MealCompletionError as exc:
        raise _completion_error(exc) from exc
    completion.reopened_by_user_id = membership.user_id
    completion.reopened_at = datetime.now(UTC)
    completion.reopen_reason = reason

    lines = list(
        session.scalars(
            select(MealCompletionLine).where(
                MealCompletionLine.meal_completion_id == completion.id,
                MealCompletionLine.household_id == membership.household_id,
            )
        )
    )
    try:
        for line in lines:
            _reverse_line_consumption(session, membership, line.id, operation)
        session.flush()
        result = _completion_payload(session, completion)
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        replay = _commit_or_replay(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The completion changed since it was loaded.",
        )
    except DomainError:
        session.rollback()
        raise
    except IntegrityError as exc:
        session.rollback()
        raise DomainError(
            "conflict",
            "Meal completion conflict",
            "The completion changed since it was loaded.",
            409,
        ) from exc
    if replay is not None:
        return CompletionMutationResult(replay)
    return CompletionMutationResult(result)
