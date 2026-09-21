from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.planning.policies import MealPlanState
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.planning_models import (
    MealPlan,
    MealPlanOperation,
    MealPlanStateEvent,
)

WEEK = date(2026, 9, 28)


def _seed_household(session: Session) -> tuple:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="Planning", locale="es", timezone="UTC"))
    session.add(
        HouseholdMember(
            household_id=household_id,
            user_id=user_id,
            role=MembershipRole.OWNER,
            status=MembershipStatus.ACTIVE,
        )
    )
    session.flush()
    return user_id, household_id


def _add_plan(session: Session, household_id, user_id, state=MealPlanState.DRAFT) -> MealPlan:
    plan = MealPlan(
        id=uuid4(),
        household_id=household_id,
        week_start_date=WEEK,
        state=state,
        created_by_user_id=user_id,
    )
    session.add(plan)
    session.flush()
    return plan


@pytest.mark.integration
def test_planning_schema_structure(integration_engine) -> None:
    inspector = inspect(integration_engine)
    tables = set(inspector.get_table_names())
    assert {
        "meal_plan",
        "meal_plan_entry",
        "meal_plan_state_event",
        "meal_plan_operation",
    }.issubset(tables)

    plan_indexes = {item["name"] for item in inspector.get_indexes("meal_plan")}
    assert "ix_meal_plan_active_week" in plan_indexes

    entry_constraints = {
        item["name"] for item in inspector.get_unique_constraints("meal_plan_entry")
    }
    assert "uq_meal_plan_entry_slot" in entry_constraints

    event_checks = {
        item["name"] for item in inspector.get_check_constraints("meal_plan_state_event")
    }
    assert {
        "ck_meal_plan_state_event_from_state",
        "ck_meal_plan_state_event_to_state",
    }.issubset(event_checks)

    event_fks = {item["name"] for item in inspector.get_foreign_keys("meal_plan_state_event")}
    assert "fk_meal_plan_state_event_plan_household" in event_fks

    operation_constraints = {
        item["name"] for item in inspector.get_unique_constraints("meal_plan_operation")
    }
    assert "uq_meal_plan_operation_idempotency" in operation_constraints

    with integration_engine.connect() as connection:
        trigger = connection.execute(
            text("SELECT 1 FROM pg_trigger WHERE tgname = 'meal_plan_state_event_append_only'")
        ).scalar_one_or_none()
    assert trigger == 1


@pytest.mark.integration
def test_state_event_rejects_invalid_from_state(integration_engine) -> None:
    with Session(integration_engine) as session:
        user_id, household_id = _seed_household(session)
        plan = _add_plan(session, household_id, user_id)
        session.commit()
        with pytest.raises(IntegrityError):
            with session.begin():
                session.execute(
                    text(
                        "INSERT INTO meal_plan_state_event "
                        "(id, household_id, meal_plan_id, from_state, to_state, actor_user_id) "
                        "VALUES (:id, :household_id, :plan_id, 'bogus', 'approved', :actor)"
                    ),
                    {
                        "id": uuid4(),
                        "household_id": household_id,
                        "plan_id": plan.id,
                        "actor": user_id,
                    },
                )


@pytest.mark.integration
def test_state_event_is_append_only(integration_engine) -> None:
    with Session(integration_engine) as session:
        user_id, household_id = _seed_household(session)
        plan = _add_plan(session, household_id, user_id)
        event = MealPlanStateEvent(
            household_id=household_id,
            meal_plan_id=plan.id,
            from_state=MealPlanState.DRAFT,
            to_state=MealPlanState.PROPOSED,
            actor_user_id=user_id,
        )
        session.add(event)
        session.commit()

        with pytest.raises(Exception, match="append-only"):
            with session.begin():
                session.execute(
                    text("UPDATE meal_plan_state_event SET note = 'x' WHERE id = :id"),
                    {"id": event.id},
                )
        with pytest.raises(Exception, match="append-only"):
            with session.begin():
                session.execute(
                    text("DELETE FROM meal_plan_state_event WHERE id = :id"),
                    {"id": event.id},
                )


@pytest.mark.integration
def test_only_one_active_plan_per_week(integration_engine) -> None:
    with Session(integration_engine) as session:
        user_id, household_id = _seed_household(session)
        _add_plan(session, household_id, user_id)
        session.commit()
        with pytest.raises(IntegrityError):
            with session.begin():
                _add_plan(session, household_id, user_id)
        with session.begin():
            _add_plan(session, household_id, user_id, state=MealPlanState.ARCHIVED)


@pytest.mark.integration
def test_operation_idempotency_key_is_unique_per_household(integration_engine) -> None:
    with Session(integration_engine) as session:
        user_id, household_id = _seed_household(session)
        session.commit()
        key = f"key-{uuid4()}"
        session.add(
            MealPlanOperation(
                household_id=household_id,
                operation="meal_plan_create",
                idempotency_key=key,
                request_hash="a" * 64,
            )
        )
        session.commit()
        with pytest.raises(IntegrityError):
            with session.begin():
                session.add(
                    MealPlanOperation(
                        household_id=household_id,
                        operation="meal_plan_create",
                        idempotency_key=key,
                        request_hash="b" * 64,
                    )
                )
