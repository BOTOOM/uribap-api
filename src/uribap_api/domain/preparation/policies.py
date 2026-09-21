from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from uribap_api.domain.inventory.ledger import InventoryLedgerError, quantize_amount
from uribap_api.domain.recipes.policies import PreparationRuleType, RecipeMealType
from uribap_api.domain.shared.fingerprint import operation_fingerprint


class PreparationError(ValueError):
    pass


class PreparationTaskStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PreparationTaskOrigin(StrEnum):
    DERIVED = "derived"
    MANUAL = "manual"


class PreparationTaskType(StrEnum):
    DEFROST = "defrost"
    SOAK = "soak"
    MARINATE = "marinate"
    PREPARE_AHEAD = "prepare_ahead"
    MANUAL = "manual"


class PreparationTaskAction(StrEnum):
    COMPLETE = "complete"
    CANCEL = "cancel"


MEAL_START_TIMES: dict[RecipeMealType, time] = {
    RecipeMealType.BREAKFAST: time(8, 0),
    RecipeMealType.LUNCH: time(13, 0),
    RecipeMealType.SNACK: time(17, 0),
    RecipeMealType.DINNER: time(20, 0),
}

MAX_LEAD_MINUTES = 7 * 24 * 60

_TASK_TRANSITIONS: dict[
    PreparationTaskAction, tuple[frozenset[PreparationTaskStatus], PreparationTaskStatus]
] = {
    PreparationTaskAction.COMPLETE: (
        frozenset({PreparationTaskStatus.PENDING}),
        PreparationTaskStatus.COMPLETED,
    ),
    PreparationTaskAction.CANCEL: (
        frozenset({PreparationTaskStatus.PENDING}),
        PreparationTaskStatus.CANCELLED,
    ),
}


def apply_task_transition(
    status: PreparationTaskStatus, action: PreparationTaskAction
) -> PreparationTaskStatus:
    allowed, target = _TASK_TRANSITIONS[action]
    if status not in allowed:
        raise PreparationError(f"cannot {action} a task in status {status}")
    return target


def assert_version(expected: int, current: int) -> int:
    if expected != current:
        raise PreparationError("the task changed since it was loaded")
    return current + 1


def resolve_timezone(name: str | None) -> ZoneInfo:
    if name:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError, ValueError:
            pass
    return ZoneInfo("UTC")


def validate_lead_minutes(minutes: int) -> int:
    if minutes < 0:
        raise PreparationError("lead minutes cannot be negative")
    if minutes > MAX_LEAD_MINUTES:
        raise PreparationError(f"lead minutes cannot exceed {MAX_LEAD_MINUTES}")
    return minutes


def compute_due_at(
    planned_date: date,
    meal_type: RecipeMealType,
    lead_minutes: int,
    timezone_name: str | None,
) -> datetime:
    validate_lead_minutes(lead_minutes)
    start = MEAL_START_TIMES.get(meal_type)
    if start is None:
        raise PreparationError(f"unknown meal type {meal_type}")
    tz = resolve_timezone(timezone_name)
    meal_start = datetime.combine(planned_date, start, tzinfo=tz)
    return (meal_start - timedelta(minutes=lead_minutes)).astimezone(UTC)


def derived_fingerprint(entry_id: UUID, rule_id: UUID) -> str:
    return operation_fingerprint(
        "preparation_derived",
        {"meal_plan_entry_id": str(entry_id), "rule_id": str(rule_id)},
    )


def rule_type_to_task_type(rule_type: PreparationRuleType) -> PreparationTaskType:
    return PreparationTaskType(rule_type.value)


def validate_manual_task(
    title: str,
    amount: Decimal | None,
    unit: str | None,
) -> tuple[str, Decimal | None, str | None]:
    normalized_title = title.strip()
    if not normalized_title:
        raise PreparationError("title is required")
    if len(normalized_title) > 200:
        raise PreparationError("title must not exceed 200 characters")
    if (amount is None) != (unit is None):
        raise PreparationError("amount and unit must be provided together")
    normalized_amount: Decimal | None = None
    if amount is not None:
        try:
            normalized_amount = quantize_amount(amount, allow_zero=False)
        except InventoryLedgerError as exc:
            raise PreparationError(str(exc)) from exc
    normalized_unit = unit.strip() if unit is not None else None
    if normalized_unit is not None and not normalized_unit:
        raise PreparationError("unit must not be empty")
    return normalized_title, normalized_amount, normalized_unit
