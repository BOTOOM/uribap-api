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


def _task(
    session: Session,
    household_id: str,
    user_id: str,
    *,
    origin: str = "manual",
    task_type: str = "manual",
    status: str = "pending",
    entry_id: str | None = None,
    fingerprint: str | None = None,
) -> str:
    task_id = uuid4()
    session.execute(
        text(
            "INSERT INTO preparation_task (id, household_id, origin, task_type, title, due_at, "
            "status, version, meal_plan_entry_id, fingerprint, created_by_user_id) VALUES (:id, "
            ":hid, :origin, :tt, 'Task', :due, :status, 1, :eid, :fp, :uid)"
        ),
        {
            "id": task_id,
            "hid": household_id,
            "origin": origin,
            "tt": task_type,
            "due": datetime.now(UTC),
            "status": status,
            "eid": entry_id,
            "fp": fingerprint,
            "uid": user_id,
        },
    )
    session.flush()
    return str(task_id)


@pytest.mark.integration
def test_preparation_tables_exist_with_expected_columns(integration_engine) -> None:
    with integration_engine.connect() as connection:
        for table, columns in {
            "preparation_task": {
                "id",
                "household_id",
                "origin",
                "task_type",
                "title",
                "due_at",
                "status",
                "version",
                "meal_plan_entry_id",
                "fingerprint",
                "completed_by_user_id",
            },
            "preparation_operation": {
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
def test_preparation_task_check_constraints(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        entry_id = _entry(session, household_id, user_id)
        session.commit()

        for kwargs in (
            {"origin": "bogus"},
            {"task_type": "bogus"},
            {"status": "bogus"},
            {"origin": "derived", "task_type": "defrost", "fingerprint": "f"},  # no entry
            {"origin": "derived", "task_type": "defrost", "entry_id": entry_id},  # no fingerprint
            {"status": "completed"},  # no completed fields
        ):
            with pytest.raises(IntegrityError), session.begin_nested():
                _task(session, household_id, user_id, **kwargs)

        # amount without unit violates the pair CHECK
        with pytest.raises(IntegrityError), session.begin_nested():
            task_id = _task(session, household_id, user_id)
            session.execute(
                text("UPDATE preparation_task SET amount = 3 WHERE id = :id"), {"id": task_id}
            )

        _task(session, household_id, user_id)
        _task(
            session,
            household_id,
            user_id,
            origin="derived",
            task_type="defrost",
            entry_id=entry_id,
            fingerprint="fp-ok",
        )
        session.rollback()


@pytest.mark.integration
def test_derived_fingerprint_partial_uniqueness(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        entry_id = _entry(session, household_id, user_id)
        session.commit()

        _task(
            session,
            household_id,
            user_id,
            origin="derived",
            task_type="soak",
            entry_id=entry_id,
            fingerprint="fp-1",
        )
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            _task(
                session,
                household_id,
                user_id,
                origin="derived",
                task_type="soak",
                entry_id=entry_id,
                fingerprint="fp-1",
            )

        # manual rows may repeat a NULL fingerprint freely
        _task(session, household_id, user_id)
        _task(session, household_id, user_id)
        session.rollback()


@pytest.mark.integration
def test_entry_composite_fk_enforces_tenant(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        other_id, other_user = _household(session)
        foreign_entry = _entry(session, other_id, other_user)
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            _task(
                session,
                household_id,
                user_id,
                origin="derived",
                task_type="marinate",
                entry_id=foreign_entry,
                fingerprint="fp-x",
            )

        own_entry = _entry(session, household_id, user_id)
        _task(
            session,
            household_id,
            user_id,
            origin="derived",
            task_type="marinate",
            entry_id=own_entry,
            fingerprint="fp-y",
        )
        session.rollback()


@pytest.mark.integration
def test_preparation_operation_idempotency_uniqueness(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, _user_id = _household(session)
        session.execute(
            text(
                "INSERT INTO preparation_operation (id, household_id, operation, "
                "idempotency_key) VALUES (:id, :hid, 'complete_task', 'k1')"
            ),
            {"id": uuid4(), "hid": household_id},
        )
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(
                text(
                    "INSERT INTO preparation_operation (id, household_id, operation, "
                    "idempotency_key) VALUES (:id, :hid, 'complete_task', 'k1')"
                ),
                {"id": uuid4(), "hid": household_id},
            )
