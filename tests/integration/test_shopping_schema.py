from datetime import UTC, date, datetime
from decimal import Decimal
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


def _ingredient(session: Session, household_id: str) -> str:
    ingredient_id = uuid4()
    session.execute(
        text(
            "INSERT INTO ingredient (id, household_id, name, normalized_name, dimension, "
            "base_unit) VALUES (:id, :hid, :name, :norm, 'mass', 'g')"
        ),
        {"id": ingredient_id, "hid": household_id, "name": f"Ing {uuid4()}", "norm": str(uuid4())},
    )
    session.flush()
    return str(ingredient_id)


def _list(session: Session, household_id: str, user_id: str, from_date: date) -> str:
    list_id = uuid4()
    session.execute(
        text(
            "INSERT INTO shopping_list (id, household_id, from_date, to_date, state, version, "
            "created_by_user_id) VALUES (:id, :hid, :fd, :td, 'open', 1, :uid)"
        ),
        {"id": list_id, "hid": household_id, "fd": from_date, "td": from_date, "uid": user_id},
    )
    session.flush()
    return str(list_id)


def _item(
    session: Session, household_id: str, list_id: str, ingredient_id: str, status: str = "pending"
) -> str:
    item_id = uuid4()
    session.execute(
        text(
            "INSERT INTO shopping_item (id, household_id, shopping_list_id, ingredient_id, unit, "
            "needed_amount, optional_amount, status, position) VALUES (:id, :hid, :lid, :iid, "
            "'g', 10, 0, :status, 0)"
        ),
        {
            "id": item_id,
            "hid": household_id,
            "lid": list_id,
            "iid": ingredient_id,
            "status": status,
        },
    )
    session.flush()
    return str(item_id)


@pytest.mark.integration
def test_shopping_tables_exist_with_expected_columns(integration_engine) -> None:
    with integration_engine.connect() as connection:
        for table, columns in {
            "shopping_list": {"id", "household_id", "from_date", "to_date", "state", "version"},
            "shopping_item": {
                "id",
                "household_id",
                "shopping_list_id",
                "ingredient_id",
                "unit",
                "needed_amount",
                "status",
                "purchased_lot_id",
            },
            "shopping_operation": {
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
def test_shopping_item_status_and_purchase_checks(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        list_id = _list(session, household_id, user_id, date(2027, 3, 1))
        ingredient_id = _ingredient(session, household_id)
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            _item(session, household_id, list_id, ingredient_id, status="bogus")

        # purchased status without purchase fields violates the invariant CHECK
        with pytest.raises(IntegrityError), session.begin_nested():
            _item(session, household_id, list_id, ingredient_id, status="purchased")

        _item(session, household_id, list_id, ingredient_id, status="pending")
        session.rollback()


@pytest.mark.integration
def test_unique_active_window_per_household(integration_engine) -> None:
    day = date(2027, 3, 8)
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        first = _list(session, household_id, user_id, day)
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            _list(session, household_id, user_id, day)

        # an archived list does not block a new live list for the same window
        session.execute(
            text("UPDATE shopping_list SET state = 'archived' WHERE id = :id"), {"id": first}
        )
        _list(session, household_id, user_id, day)
        session.rollback()


@pytest.mark.integration
def test_shopping_operation_idempotency_uniqueness(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, _user_id = _household(session)
        session.execute(
            text(
                "INSERT INTO shopping_operation (id, household_id, operation, idempotency_key) "
                "VALUES (:id, :hid, 'purchase_item', 'k1')"
            ),
            {"id": uuid4(), "hid": household_id},
        )
        session.commit()

        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(
                text(
                    "INSERT INTO shopping_operation (id, household_id, operation, "
                    "idempotency_key) VALUES (:id, :hid, 'purchase_item', 'k1')"
                ),
                {"id": uuid4(), "hid": household_id},
            )


@pytest.mark.integration
def test_purchased_lot_must_exist_and_item_links(integration_engine) -> None:
    with Session(integration_engine) as session:
        household_id, user_id = _household(session)
        list_id = _list(session, household_id, user_id, date(2027, 3, 15))
        ingredient_id = _ingredient(session, household_id)
        item_id = _item(session, household_id, list_id, ingredient_id)

        lot_id = uuid4()
        session.execute(
            text(
                "INSERT INTO inventory_lot (id, household_id, ingredient_id, quantity_on_hand, "
                "unit, location, available, created_by_user_id) VALUES (:id, :hid, :iid, 5, 'g', "
                "'pantry', true, :uid)"
            ),
            {"id": lot_id, "hid": household_id, "iid": ingredient_id, "uid": user_id},
        )
        session.execute(
            text(
                "UPDATE shopping_item SET status = 'purchased', purchased_amount = :amt, "
                "purchased_lot_id = :lot, purchased_at = :ts WHERE id = :id"
            ),
            {
                "amt": Decimal("5"),
                "lot": lot_id,
                "ts": datetime.now(UTC),
                "id": item_id,
            },
        )
        session.commit()

        # a nonexistent lot violates the FK
        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(
                text("UPDATE shopping_item SET purchased_lot_id = :lot WHERE id = :id"),
                {"lot": uuid4(), "id": item_id},
            )
        session.rollback()
