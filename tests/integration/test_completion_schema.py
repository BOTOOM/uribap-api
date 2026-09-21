from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def _household(session: Session) -> tuple[str, str]:
    user_id, household_id = uuid4(), uuid4()
    session.execute(
        text(
            "INSERT INTO app_user (id, email, email_verified) "
            "VALUES (:id, :email, true) ON CONFLICT DO NOTHING"
        ),
        {"id": user_id, "email": f"{user_id}@example.test"},
    )
    session.execute(
        text("INSERT INTO household (id, name, locale, timezone) VALUES (:id, 'H', 'es', 'UTC')"),
        {"id": household_id},
    )
    session.flush()
    return str(household_id), str(user_id)


def _entry(session: Session, household_id: str, user_id: str) -> str:
    recipe_id, version_id, plan_id, entry_id = uuid4(), uuid4(), uuid4(), uuid4()
    session.execute(
        text(
            "INSERT INTO recipe (id, household_id, name, normalized_name, created_by_user_id) "
            "VALUES (:id, :hid, 'R', :norm, :uid)"
        ),
        {"id": recipe_id, "hid": household_id, "norm": str(uuid4()), "uid": user_id},
    )
    session.execute(
        text(
            "INSERT INTO recipe_version (id, recipe_id, version_number, base_servings, "
            "prep_minutes, state, created_by_user_id, published_by_user_id) VALUES (:id, :rid, "
            "1, 2, 10, 'published', :uid, :uid)"
        ),
        {"id": version_id, "rid": recipe_id, "uid": user_id},
    )
    session.execute(
        text(
            "INSERT INTO meal_plan (id, household_id, week_start_date, state, version, "
            "created_by_user_id) VALUES (:id, :hid, :ws, 'approved', 1, :uid)"
        ),
        {"id": plan_id, "hid": household_id, "ws": date(2027, 5, 3), "uid": user_id},
    )
    session.execute(
        text(
            "INSERT INTO meal_plan_entry (id, household_id, meal_plan_id, planned_date, "
            "meal_type, recipe_version_id, servings, position, added_by_user_id) VALUES (:id, "
            ":hid, :pid, :pd, 'dinner', :vid, 2, 0, :uid)"
        ),
        {
            "id": entry_id,
            "hid": household_id,
            "pid": plan_id,
            "pd": date(2027, 5, 3),
            "vid": version_id,
            "uid": user_id,
        },
    )
    session.flush()
    return str(entry_id)


def _ingredient(session: Session, household_id: str, user_id: str) -> str:
    ingredient_id = uuid4()
    session.execute(
        text(
            "INSERT INTO ingredient (id, household_id, name, normalized_name, dimension, "
            "base_unit, created_by_user_id) VALUES (:id, :hid, 'I', :norm, 'mass', 'g', :uid)"
        ),
        {
            "id": ingredient_id,
            "hid": household_id,
            "norm": str(uuid4()),
            "uid": user_id,
        },
    )
    session.flush()
    return str(ingredient_id)


def _completion(
    session: Session,
    household_id: str,
    user_id: str,
    entry_id: str,
    *,
    state: str = "recorded",
) -> str:
    completion_id = uuid4()
    params: dict[str, object] = {
        "id": completion_id,
        "hid": household_id,
        "eid": entry_id,
        "uid": user_id,
        "now": datetime.now(UTC),
        "state": state,
    }
    columns = (
        "id, household_id, meal_plan_entry_id, state, version, completed_by_user_id, "
        "completed_at"
    )
    values = ":id, :hid, :eid, :state, 1, :uid, :now"
    if state == "reopened":
        columns += ", reopened_by_user_id, reopened_at"
        values += ", :uid, :now"
    session.execute(
        text(f"INSERT INTO meal_completion ({columns}) VALUES ({values})"),
        params,
    )
    session.flush()
    return str(completion_id)


def _line(
    session: Session,
    household_id: str,
    completion_id: str,
    ingredient_id: str,
    *,
    unit: str = "kg",
    actual: float = 1.0,
) -> str:
    line_id = uuid4()
    session.execute(
        text(
            "INSERT INTO meal_completion_line (id, household_id, meal_completion_id, "
            "ingredient_id, planned_amount, actual_amount, unit, optional, position) "
            "VALUES (:id, :hid, :cid, :iid, 1, :actual, :unit, false, 0)"
        ),
        {
            "id": line_id,
            "hid": household_id,
            "cid": completion_id,
            "iid": ingredient_id,
            "actual": actual,
            "unit": unit,
        },
    )
    session.flush()
    return str(line_id)


@pytest.mark.integration
def test_completion_tables_exist_with_expected_columns(integration_engine) -> None:
    with integration_engine.connect() as connection:
        for table, columns in {
            "meal_completion": {
                "id",
                "household_id",
                "meal_plan_entry_id",
                "state",
                "version",
                "completed_by_user_id",
                "completed_at",
                "reopened_by_user_id",
                "reopened_at",
                "reopen_reason",
            },
            "meal_completion_line": {
                "id",
                "household_id",
                "meal_completion_id",
                "ingredient_id",
                "planned_amount",
                "actual_amount",
                "unit",
                "optional",
                "position",
            },
            "completion_operation": {
                "id",
                "household_id",
                "operation",
                "idempotency_key",
                "request_hash",
                "result_payload",
            },
        }.items():
            rows = connection.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
                {"t": table},
            )
            assert columns <= {row[0] for row in rows}


@pytest.mark.integration
def test_completion_check_constraints(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        entry_id = _entry(session, household_id, user_id)
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            _completion(session, household_id, user_id, entry_id, state="bogus")

        # reopened without reopened fields violates the CHECK
        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(
                text(
                    "INSERT INTO meal_completion (id, household_id, meal_plan_entry_id, "
                    "state, version, completed_by_user_id, completed_at) VALUES (:id, :hid, "
                    ":eid, 'reopened', 1, :uid, :now)"
                ),
                {
                    "id": uuid4(),
                    "hid": household_id,
                    "eid": entry_id,
                    "uid": user_id,
                    "now": datetime.now(UTC),
                },
            )

        _completion(session, household_id, user_id, entry_id)
        session.rollback()


@pytest.mark.integration
def test_one_recorded_completion_per_entry(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        entry_id = _entry(session, household_id, user_id)
        session.commit()

        completion_id = _completion(session, household_id, user_id, entry_id)
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            _completion(session, household_id, user_id, entry_id)

        # reopening the row frees the entry for a new recorded completion
        session.execute(
            text(
                "UPDATE meal_completion SET state = 'reopened', "
                "reopened_by_user_id = :uid, reopened_at = :now WHERE id = :id"
            ),
            {"uid": user_id, "now": datetime.now(UTC), "id": completion_id},
        )
        _completion(session, household_id, user_id, entry_id)
        session.rollback()


@pytest.mark.integration
def test_completion_line_constraints_and_composite_fk(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        other_id, other_user = _household(session)
        entry_id = _entry(session, household_id, user_id)
        ingredient_id = _ingredient(session, household_id, user_id)
        session.commit()

        completion_id = _completion(session, household_id, user_id, entry_id)
        foreign_completion = _completion(session, other_id, other_user, _entry(session, other_id, other_user))
        session.commit()

        # cross-tenant completion reference is rejected by the composite FK
        with pytest.raises(IntegrityError), session.begin_nested():
            _line(session, household_id, foreign_completion, ingredient_id)

        # non-positive actual amount is rejected
        with pytest.raises(IntegrityError), session.begin_nested():
            _line(session, household_id, completion_id, ingredient_id, actual=0)

        # duplicate (ingredient, unit) per completion is rejected
        _line(session, household_id, completion_id, ingredient_id)
        with pytest.raises(IntegrityError), session.begin_nested():
            _line(session, household_id, completion_id, ingredient_id)
        session.rollback()


@pytest.mark.integration
def test_completion_operation_idempotency_uniqueness(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, _user_id = _household(session)
        session.execute(
            text(
                "INSERT INTO completion_operation (id, household_id, operation, "
                "idempotency_key) VALUES (:id, :hid, 'meal_entry_complete', 'k1')"
            ),
            {"id": uuid4(), "hid": household_id},
        )
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(
                text(
                    "INSERT INTO completion_operation (id, household_id, operation, "
                    "idempotency_key) VALUES (:id, :hid, 'meal_entry_complete', 'k1')"
                ),
                {"id": uuid4(), "hid": household_id},
            )
