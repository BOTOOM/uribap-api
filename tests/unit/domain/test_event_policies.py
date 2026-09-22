from datetime import timedelta
from uuid import uuid4

import pytest

from uribap_api.domain.events.policies import (
    MAX_DELIVERY_ATTEMPTS,
    DeliveryDecision,
    DomainEventKind,
    build_event,
    decide_delivery,
    next_attempt_delay,
    scrub_payload,
    subject_for,
)


def test_event_kind_catalog_is_stable() -> None:
    assert DomainEventKind.MEMBER_ADDED == "household.member_added"
    assert DomainEventKind.PLAN_APPROVED == "plan.approved"
    assert DomainEventKind.SHOPPING_PURCHASED == "shopping.purchased"
    assert DomainEventKind.PREPARATION_COMPLETED == "preparation.task_completed"
    assert DomainEventKind.MEAL_COMPLETED == "meal.completed"
    assert DomainEventKind.MEAL_LINE_CORRECTED == "meal.line_corrected"


def test_build_event_scrubs_and_shapes_payload() -> None:
    actor = uuid4()
    aggregate = uuid4()
    event = build_event(
        DomainEventKind.PLAN_APPROVED,
        actor_user_id=actor,
        aggregate_type="meal_plan",
        aggregate_id=aggregate,
        payload={"plan_id": str(aggregate), "token": "nope", "entries": 7},
        request_id="req-1",
    )
    assert event.kind is DomainEventKind.PLAN_APPROVED
    assert event.actor_user_id == actor
    assert event.aggregate_id == aggregate
    assert event.payload == {"plan_id": str(aggregate), "entries": 7}
    assert event.request_id == "req-1"


def test_scrub_payload_removes_denylisted_keys_case_insensitive() -> None:
    payload = {
        "Authorization": "x",
        "COOKIE": "y",
        "Token": "z",
        "secret": "s",
        "Password": "p",
        "keep": 1,
    }
    assert scrub_payload(payload) == {"keep": 1}


def test_decide_delivery_suppresses_when_disabled() -> None:
    assert decide_delivery(delivery_enabled=False) is DeliveryDecision.SUPPRESSED
    assert decide_delivery(delivery_enabled=True) is DeliveryDecision.SEND


def test_next_attempt_delay_grows_exponentially_and_caps() -> None:
    assert next_attempt_delay(1) == timedelta(seconds=30)
    assert next_attempt_delay(2) == timedelta(seconds=60)
    assert next_attempt_delay(3) == timedelta(seconds=120)
    assert next_attempt_delay(50) == timedelta(hours=1)


def test_next_attempt_delay_rejects_non_positive_attempts() -> None:
    with pytest.raises(ValueError):
        next_attempt_delay(0)


def test_subject_for_known_and_unknown_kinds() -> None:
    assert subject_for("household_invitation") == "Uribap household invitation"
    assert subject_for("verification") == "Uribap verification"
    assert subject_for("custom_kind") == "Uribap notification"


def test_max_delivery_attempts_is_positive() -> None:
    assert MAX_DELIVERY_ATTEMPTS >= 1
