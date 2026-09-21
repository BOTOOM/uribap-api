from datetime import date
from uuid import uuid4

import pytest

from uribap_api.domain.planning.policies import (
    MealPlanAction,
    MealPlanningError,
    MealPlanState,
    apply_transition,
    assert_version,
    can_edit_entries,
    validate_planned_date,
    validate_servings,
    validate_week_start,
)
from uribap_api.domain.shared.fingerprint import operation_fingerprint

MONDAY = date(2026, 9, 28)


def test_state_machine_allows_and_rejects_transitions() -> None:
    actor, other = uuid4(), uuid4()
    assert (
        apply_transition(
            MealPlanState.DRAFT,
            MealPlanAction.PROPOSE,
            actor_id=actor,
            proposed_by=None,
            active_member_count=1,
            note=None,
        )
        == MealPlanState.PROPOSED
    )
    with pytest.raises(MealPlanningError):
        apply_transition(
            MealPlanState.DRAFT,
            MealPlanAction.APPROVE,
            actor_id=actor,
            proposed_by=None,
            active_member_count=1,
            note=None,
        )
    with pytest.raises(MealPlanningError):
        apply_transition(
            MealPlanState.ARCHIVED,
            MealPlanAction.PROPOSE,
            actor_id=actor,
            proposed_by=None,
            active_member_count=1,
            note=None,
        )
    assert can_edit_entries(MealPlanState.DRAFT)
    assert not can_edit_entries(MealPlanState.PROPOSED)
    assert not can_edit_entries(MealPlanState.APPROVED)


def test_approval_requires_a_different_member_in_multi_member_household() -> None:
    proposer, approver = uuid4(), uuid4()
    assert (
        apply_transition(
            MealPlanState.PROPOSED,
            MealPlanAction.APPROVE,
            actor_id=proposer,
            proposed_by=proposer,
            active_member_count=1,
            note=None,
        )
        == MealPlanState.APPROVED
    )
    with pytest.raises(MealPlanningError):
        apply_transition(
            MealPlanState.PROPOSED,
            MealPlanAction.APPROVE,
            actor_id=proposer,
            proposed_by=proposer,
            active_member_count=2,
            note=None,
        )
    assert (
        apply_transition(
            MealPlanState.PROPOSED,
            MealPlanAction.APPROVE,
            actor_id=approver,
            proposed_by=proposer,
            active_member_count=2,
            note=None,
        )
        == MealPlanState.APPROVED
    )


def test_reopen_from_approved_requires_a_note() -> None:
    actor = uuid4()
    with pytest.raises(MealPlanningError):
        apply_transition(
            MealPlanState.APPROVED,
            MealPlanAction.REOPEN,
            actor_id=actor,
            proposed_by=None,
            active_member_count=1,
            note=None,
        )
    assert (
        apply_transition(
            MealPlanState.APPROVED,
            MealPlanAction.REOPEN,
            actor_id=actor,
            proposed_by=None,
            active_member_count=1,
            note="guests changed",
        )
        == MealPlanState.DRAFT
    )


def test_version_conflict_and_increment() -> None:
    assert assert_version(3, 3) == 4
    with pytest.raises(MealPlanningError):
        assert_version(2, 3)


def test_week_start_and_planned_date_bounds() -> None:
    assert validate_week_start(MONDAY) == MONDAY
    with pytest.raises(MealPlanningError):
        validate_week_start(date(2026, 9, 29))
    assert validate_planned_date(MONDAY, MONDAY) == MONDAY
    assert validate_planned_date(date(2026, 10, 4), MONDAY) == date(2026, 10, 4)
    with pytest.raises(MealPlanningError):
        validate_planned_date(date(2026, 10, 5), MONDAY)


def test_servings_must_be_positive() -> None:
    assert validate_servings(2) == 2
    with pytest.raises(MealPlanningError):
        validate_servings(0)


def test_operation_fingerprint_is_stable_and_payload_sensitive() -> None:
    first = operation_fingerprint("meal_plan_entry_create", {"servings": 2, "planned_date": "2026-09-29"})
    same = operation_fingerprint("meal_plan_entry_create", {"planned_date": "2026-09-29", "servings": 2})
    different = operation_fingerprint("meal_plan_entry_create", {"servings": 3, "planned_date": "2026-09-29"})
    assert first == same
    assert first != different
