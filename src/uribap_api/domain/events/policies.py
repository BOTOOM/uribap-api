from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

DENYLISTED_KEYS = frozenset({"authorization", "cookie", "token", "secret", "password"})

MAX_DELIVERY_ATTEMPTS = 5

_BASE_DELAY = timedelta(seconds=30)
_MAX_DELAY = timedelta(hours=1)

_SUBJECTS = {
    "household_invitation": "Uribap household invitation",
    "verification": "Uribap verification",
    "password_reset": "Uribap password reset",
}


class DomainEventKind(StrEnum):
    MEMBER_ADDED = "household.member_added"
    MEMBER_REMOVED = "household.member_removed"
    INVITATION_CREATED = "invitation.created"
    INVITATION_ACCEPTED = "invitation.accepted"
    INVITATION_REVOKED = "invitation.revoked"
    PLAN_APPROVED = "plan.approved"
    PLAN_REOPENED = "plan.reopened"
    SHOPPING_PURCHASED = "shopping.purchased"
    PREPARATION_COMPLETED = "preparation.task_completed"
    PREPARATION_CANCELLED = "preparation.task_cancelled"
    MEAL_COMPLETED = "meal.completed"
    MEAL_REOPENED = "meal.reopened"
    MEAL_LINE_CORRECTED = "meal.line_corrected"


class DeliveryDecision(StrEnum):
    SEND = "send"
    SUPPRESSED = "suppressed"


@dataclass(frozen=True)
class DomainEvent:
    kind: DomainEventKind
    actor_user_id: UUID | None
    aggregate_type: str
    aggregate_id: UUID | None
    payload: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""


def scrub_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key.casefold() not in DENYLISTED_KEYS}


def build_event(
    kind: DomainEventKind,
    *,
    actor_user_id: UUID | None,
    aggregate_type: str,
    aggregate_id: UUID | None,
    payload: dict[str, Any] | None = None,
    request_id: str = "",
) -> DomainEvent:
    return DomainEvent(
        kind=kind,
        actor_user_id=actor_user_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=scrub_payload(payload or {}),
        request_id=request_id,
    )


def decide_delivery(*, delivery_enabled: bool) -> DeliveryDecision:
    return DeliveryDecision.SEND if delivery_enabled else DeliveryDecision.SUPPRESSED


def next_attempt_delay(attempt_number: int) -> timedelta:
    if attempt_number < 1:
        raise ValueError("attempt_number must be >= 1")
    base_seconds = _BASE_DELAY.total_seconds()
    cap_seconds = _MAX_DELAY.total_seconds()
    return timedelta(seconds=min(base_seconds * (2 ** (attempt_number - 1)), cap_seconds))


def subject_for(kind: str) -> str:
    return _SUBJECTS.get(kind, "Uribap notification")
