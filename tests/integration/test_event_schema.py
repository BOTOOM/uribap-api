from datetime import UTC, datetime
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


def _event(
    session: Session,
    household_id: str,
    user_id: str | None,
    *,
    kind: str = "plan.approved",
    aggregate_type: str = "meal_plan",
) -> str:
    event_id = uuid4()
    session.execute(
        text(
            "INSERT INTO domain_event (id, household_id, kind, actor_user_id, "
            "aggregate_type, aggregate_id, payload, request_id, occurred_at) "
            "VALUES (:id, :hid, :kind, :uid, :atype, :aid, '{}'::jsonb, 'req', :now)"
        ),
        {
            "id": event_id,
            "hid": household_id,
            "kind": kind,
            "uid": user_id,
            "atype": aggregate_type,
            "aid": uuid4(),
            "now": datetime.now(UTC),
        },
    )
    session.flush()
    return str(event_id)


def _outbox(session: Session, *, status: str = "pending") -> str:
    entry_id = uuid4()
    session.execute(
        text(
            "INSERT INTO email_outbox_entry (id, dedupe_key, kind, recipient_email, "
            "template_data, status) VALUES (:id, :dk, 'household_invitation', "
            ":email, '{}'::json, :status)"
        ),
        {
            "id": entry_id,
            "dk": f"test:{entry_id}",
            "email": "a@example.test",
            "status": status,
        },
    )
    session.flush()
    return str(entry_id)


def test_domain_event_insert_and_read(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        event_id = _event(session, household_id, user_id)
        session.commit()

        row = session.execute(
            text("SELECT kind, aggregate_type, request_id FROM domain_event WHERE id = :id"),
            {"id": event_id},
        ).one()
        assert row == ("plan.approved", "meal_plan", "req")


def test_domain_event_rejects_empty_kind(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            _event(session, household_id, user_id, kind="   ")


def test_domain_event_household_cascade(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        _event(session, household_id, user_id)
        session.commit()

        session.execute(text("DELETE FROM household WHERE id = :id"), {"id": household_id})
        remaining = session.execute(
            text("SELECT count(*) FROM domain_event WHERE household_id = :id"),
            {"id": household_id},
        ).scalar_one()
        assert remaining == 0


def test_outbox_accepts_suppressed_status(integration_engine) -> None:
    with Session(integration_engine) as session:
        _household(session)
        entry_id = _outbox(session, status="suppressed")
        session.commit()

        status = session.execute(
            text("SELECT status FROM email_outbox_entry WHERE id = :id"), {"id": entry_id}
        ).scalar_one()
        assert status == "suppressed"


def test_email_delivery_intent_insert(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, _ = _household(session)
        entry_id = _outbox(session)
        session.execute(
            text(
                "INSERT INTO email_delivery_intent (id, email_outbox_entry_id, "
                "household_id, outcome, subject, attempt_number) VALUES (:id, :eid, "
                ":hid, 'suppressed', 'Uribap household invitation', 1)"
            ),
            {"id": uuid4(), "eid": entry_id, "hid": household_id},
        )
        session.commit()

        outcome = session.execute(
            text("SELECT outcome FROM email_delivery_intent WHERE email_outbox_entry_id = :id"),
            {"id": entry_id},
        ).scalar_one()
        assert outcome == "suppressed"


def test_email_delivery_intent_rejects_bad_outcome(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, _ = _household(session)
        entry_id = _outbox(session)
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(
                text(
                    "INSERT INTO email_delivery_intent (id, email_outbox_entry_id, "
                    "household_id, outcome, subject, attempt_number) VALUES (:id, :eid, "
                    ":hid, 'bogus', 'x', 1)"
                ),
                {"id": uuid4(), "eid": entry_id, "hid": household_id},
            )
