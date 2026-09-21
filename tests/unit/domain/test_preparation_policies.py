from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from uribap_api.domain.preparation.policies import (
    MAX_LEAD_MINUTES,
    PreparationError,
    PreparationTaskAction,
    PreparationTaskStatus,
    PreparationTaskType,
    apply_task_transition,
    assert_version,
    compute_due_at,
    derived_fingerprint,
    resolve_timezone,
    rule_type_to_task_type,
    validate_lead_minutes,
    validate_manual_task,
)
from uribap_api.domain.recipes.policies import PreparationRuleType, RecipeMealType


def test_task_transitions() -> None:
    assert (
        apply_task_transition(PreparationTaskStatus.PENDING, PreparationTaskAction.COMPLETE)
        == PreparationTaskStatus.COMPLETED
    )
    assert (
        apply_task_transition(PreparationTaskStatus.PENDING, PreparationTaskAction.CANCEL)
        == PreparationTaskStatus.CANCELLED
    )
    for status in (PreparationTaskStatus.COMPLETED, PreparationTaskStatus.CANCELLED):
        for action in PreparationTaskAction:
            with pytest.raises(PreparationError):
                apply_task_transition(status, action)


def test_assert_version() -> None:
    assert assert_version(2, 2) == 3
    with pytest.raises(PreparationError):
        assert_version(1, 3)


def test_resolve_timezone_fallback() -> None:
    assert resolve_timezone("Europe/Madrid").key == "Europe/Madrid"
    assert resolve_timezone("not-a-zone").key == "UTC"
    assert resolve_timezone(None).key == "UTC"
    assert resolve_timezone("").key == "UTC"


def test_lead_minutes_bounds() -> None:
    assert validate_lead_minutes(0) == 0
    assert validate_lead_minutes(MAX_LEAD_MINUTES) == MAX_LEAD_MINUTES
    with pytest.raises(PreparationError):
        validate_lead_minutes(-1)
    with pytest.raises(PreparationError):
        validate_lead_minutes(MAX_LEAD_MINUTES + 1)


def test_compute_due_at_per_meal_type() -> None:
    day = date(2027, 4, 6)
    # dinner at 20:00 UTC minus 12h defrost -> 08:00 UTC same day
    assert compute_due_at(day, RecipeMealType.DINNER, 720, "UTC") == datetime(
        2027, 4, 6, 8, 0, tzinfo=UTC
    )
    # breakfast at 08:00 local with Europe/Madrid (UTC+2 in April) minus 60m -> 05:00 UTC
    assert compute_due_at(day, RecipeMealType.BREAKFAST, 60, "Europe/Madrid") == datetime(
        2027, 4, 6, 5, 0, tzinfo=UTC
    )
    # lunch 13:00, snack 17:00, zero lead
    assert compute_due_at(day, RecipeMealType.LUNCH, 0, "UTC") == datetime(
        2027, 4, 6, 13, 0, tzinfo=UTC
    )
    assert compute_due_at(day, RecipeMealType.SNACK, 0, "UTC") == datetime(
        2027, 4, 6, 17, 0, tzinfo=UTC
    )
    # lead crossing midnight: dinner 20:00 - 26h -> previous day 18:00
    assert compute_due_at(day, RecipeMealType.DINNER, 1560, "UTC") == datetime(
        2027, 4, 5, 18, 0, tzinfo=UTC
    )


def test_compute_due_at_rejects_bad_lead() -> None:
    with pytest.raises(PreparationError):
        compute_due_at(date(2027, 4, 6), RecipeMealType.DINNER, -5, "UTC")


def test_derived_fingerprint_is_deterministic() -> None:
    entry_id, rule_id = uuid4(), uuid4()
    assert derived_fingerprint(entry_id, rule_id) == derived_fingerprint(entry_id, rule_id)
    assert derived_fingerprint(entry_id, rule_id) != derived_fingerprint(rule_id, entry_id)


def test_rule_type_maps_to_task_type() -> None:
    for rule_type in PreparationRuleType:
        assert rule_type_to_task_type(rule_type) == PreparationTaskType(rule_type.value)


def test_validate_manual_task() -> None:
    title, amount, unit = validate_manual_task("  Soak beans  ", Decimal("0.5"), "kg")
    assert title == "Soak beans"
    assert amount == Decimal("0.500000")
    assert unit == "kg"

    title, amount, unit = validate_manual_task("Marinate", None, None)
    assert (title, amount, unit) == ("Marinate", None, None)

    with pytest.raises(PreparationError):
        validate_manual_task("   ", None, None)
    with pytest.raises(PreparationError):
        validate_manual_task("x" * 201, None, None)
    with pytest.raises(PreparationError):
        validate_manual_task("T", Decimal("1"), None)
    with pytest.raises(PreparationError):
        validate_manual_task("T", None, "g")
    with pytest.raises(PreparationError):
        validate_manual_task("T", Decimal("0"), "g")
    with pytest.raises(PreparationError):
        validate_manual_task("T", Decimal("-2"), "g")
