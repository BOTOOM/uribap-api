from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from uuid import UUID

from uribap_api.domain.recipes.policies import RecipeMealType


class MealPlanState(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    ARCHIVED = "archived"


class MealPlanAction(StrEnum):
    PROPOSE = "propose"
    APPROVE = "approve"
    REOPEN = "reopen"
    ARCHIVE = "archive"


class MealPlanningError(ValueError):
    pass


_TRANSITIONS: dict[MealPlanAction, tuple[frozenset[MealPlanState], MealPlanState]] = {
    MealPlanAction.PROPOSE: (frozenset({MealPlanState.DRAFT}), MealPlanState.PROPOSED),
    MealPlanAction.APPROVE: (frozenset({MealPlanState.PROPOSED}), MealPlanState.APPROVED),
    MealPlanAction.REOPEN: (
        frozenset({MealPlanState.PROPOSED, MealPlanState.APPROVED}),
        MealPlanState.DRAFT,
    ),
    MealPlanAction.ARCHIVE: (
        frozenset({MealPlanState.DRAFT, MealPlanState.PROPOSED, MealPlanState.APPROVED}),
        MealPlanState.ARCHIVED,
    ),
}

WEEK_LENGTH = timedelta(days=7)


def can_edit_entries(state: MealPlanState) -> bool:
    return state == MealPlanState.DRAFT


def apply_transition(
    state: MealPlanState,
    action: MealPlanAction,
    *,
    actor_id: UUID,
    proposed_by: UUID | None,
    active_member_count: int,
    note: str | None,
) -> MealPlanState:
    allowed, target = _TRANSITIONS[action]
    if state not in allowed:
        raise MealPlanningError(f"cannot {action} a plan in state {state}")
    if action == MealPlanAction.APPROVE and active_member_count >= 2:
        if proposed_by is None:
            raise MealPlanningError("the plan proposer is required for approval")
        if actor_id == proposed_by:
            raise MealPlanningError("the proposer cannot approve their own plan")
    if action == MealPlanAction.REOPEN and state == MealPlanState.APPROVED and not note:
        raise MealPlanningError("reopening an approved plan requires a note")
    return target


def assert_version(expected: int, current: int) -> int:
    if expected != current:
        raise MealPlanningError("the plan changed since it was loaded")
    return current + 1


def validate_week_start(value: date) -> date:
    if value.weekday() != 0:
        raise MealPlanningError("week_start_date must be a Monday")
    return value


def validate_planned_date(planned: date, week_start: date) -> date:
    if not week_start <= planned < week_start + WEEK_LENGTH:
        raise MealPlanningError("planned_date must fall inside the plan week")
    return planned


def validate_servings(servings: int) -> int:
    if servings <= 0:
        raise MealPlanningError("servings must be positive")
    return servings


@dataclass(frozen=True)
class PlanEntryDraft:
    planned_date: date
    meal_type: RecipeMealType
    recipe_version_id: UUID
    servings: int
    position: int
    notes: str | None = None

    def __post_init__(self) -> None:
        validate_servings(self.servings)
        if self.position < 0:
            raise MealPlanningError("position must not be negative")
