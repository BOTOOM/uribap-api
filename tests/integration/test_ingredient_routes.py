from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_active_household_membership
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.main import app

pytestmark = pytest.mark.integration


def _member(session: Session) -> HouseholdMember:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="Ingredient routes", locale="es", timezone="UTC"))
    member = HouseholdMember(
        household_id=household_id,
        user_id=user_id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(member)
    session.flush()
    return member


def test_ingredient_routes_create_get_update_and_list_pantry_staple(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    member = _member(session)
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)
    name = f"Salt {uuid4()}"

    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/ingredients",
                json={
                    "name": name,
                    "dimension": "mass",
                    "base_unit": "g",
                    "pantry_staple": True,
                },
            )
            assert created.status_code == 201
            created_payload = created.json()
            ingredient_id = created_payload["id"]
            assert created_payload["pantry_staple"] is True

            fetched = client.get(f"/api/v1/ingredients/{ingredient_id}")
            assert fetched.status_code == 200
            assert fetched.json()["pantry_staple"] is True

            updated = client.patch(
                f"/api/v1/ingredients/{ingredient_id}",
                json={"pantry_staple": False},
            )
            assert updated.status_code == 200
            assert updated.json()["pantry_staple"] is False

            listed = client.get("/api/v1/ingredients", params={"query": name})
            assert listed.status_code == 200
            assert len(listed.json()["items"]) == 1
            assert listed.json()["items"][0]["pantry_staple"] is False

            defaulted = client.post(
                "/api/v1/ingredients",
                json={
                    "name": f"Pepper {uuid4()}",
                    "dimension": "mass",
                    "base_unit": "g",
                },
            )
            assert defaulted.status_code == 201
            assert defaulted.json()["pantry_staple"] is False
    finally:
        session.close()


def test_global_ingredient_pantry_staple_update_remains_forbidden(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    member = _member(session)
    ingredient = Ingredient(
        household_id=None,
        name=f"Global salt {uuid4()}",
        normalized_name=f"global-salt-{uuid4()}",
        dimension=IngredientDimension.MASS,
        base_unit="g",
    )
    session.add(ingredient)
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)

    try:
        with TestClient(app) as client:
            response = client.patch(
                f"/api/v1/ingredients/{ingredient.id}",
                json={"pantry_staple": True},
            )

        assert response.status_code == 403
        assert response.json()["code"] == "forbidden"
    finally:
        session.close()
