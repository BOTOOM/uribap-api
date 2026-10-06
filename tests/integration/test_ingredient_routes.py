import base64
import json
from datetime import UTC, datetime
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


def _ingredient(
    member: HouseholdMember,
    normalized_name: str,
    *,
    global_ingredient: bool = False,
    dimension: IngredientDimension = IngredientDimension.MASS,
) -> Ingredient:
    return Ingredient(
        household_id=None if global_ingredient else member.household_id,
        name=normalized_name,
        normalized_name=normalized_name,
        dimension=dimension,
        base_unit="unit" if dimension == IngredientDimension.COUNT else "g",
        created_by_user_id=None if global_ingredient else member.user_id,
    )


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


def test_ingredient_route_paginates_ties_in_stable_two_page_order(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    member = _member(session)
    prefix = f"pagination-{uuid4().hex}"
    tied_name = f"{prefix}-middle"
    ingredients = [
        _ingredient(member, f"{prefix}-alpha"),
        _ingredient(member, tied_name, global_ingredient=True),
        _ingredient(member, tied_name),
        _ingredient(member, f"{prefix}-zulu"),
    ]
    session.add_all(ingredients)
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)
    expected_ids = [
        str(ingredient.id)
        for ingredient in sorted(
            ingredients,
            key=lambda item: (item.normalized_name, item.id.int),
        )
    ]

    try:
        with TestClient(app) as client:
            first_page = client.get(
                "/api/v1/ingredients",
                params={
                    "query": prefix,
                    "include_global": True,
                    "limit": 2,
                },
            )
            assert first_page.status_code == 200
            first_payload = first_page.json()
            assert len(first_payload["items"]) == 2
            assert first_payload["page_info"]["limit"] == 2
            assert first_payload["page_info"]["next_cursor"] is not None

            second_page = client.get(
                "/api/v1/ingredients",
                params={
                    "query": prefix,
                    "include_global": True,
                    "limit": 2,
                    "cursor": first_payload["page_info"]["next_cursor"],
                },
            )
            assert second_page.status_code == 200
            second_payload = second_page.json()
            assert len(second_payload["items"]) == 2
            assert second_payload["page_info"] == {"next_cursor": None, "limit": 2}

        actual_ids = [item["id"] for item in first_payload["items"] + second_payload["items"]]
        assert actual_ids == expected_ids
        assert len(actual_ids) == len(set(actual_ids)) == 4
    finally:
        session.close()


def test_ingredient_route_paginates_long_unicode_names_with_cursor(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    member = _member(session)
    prefix = "𝄞" * 159
    ingredients = [
        _ingredient(member, f"{prefix}𝄞"),
        _ingredient(member, f"{prefix}😀"),
    ]
    session.add_all(ingredients)
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)

    try:
        with TestClient(app) as client:
            first_page = client.get(
                "/api/v1/ingredients",
                params={"include_global": False, "limit": 1},
            )
            assert first_page.status_code == 200
            first_payload = first_page.json()
            assert len(first_payload["items"]) == 1
            assert first_payload["page_info"]["next_cursor"] is not None

            second_page = client.get(
                "/api/v1/ingredients",
                params={
                    "include_global": False,
                    "limit": 1,
                    "cursor": first_payload["page_info"]["next_cursor"],
                },
            )
            assert second_page.status_code == 200
            second_payload = second_page.json()

        actual_ids = [item["id"] for item in first_payload["items"] + second_payload["items"]]
        assert len(second_payload["items"]) == 1
        assert second_payload["page_info"]["next_cursor"] is None
        assert set(actual_ids) == {str(ingredient.id) for ingredient in ingredients}
        assert len(actual_ids) == len(set(actual_ids)) == 2
    finally:
        session.close()


def test_ingredient_route_invalid_cursor_returns_problem_details(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    member = _member(session)
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)
    invalid_cursors = [
        "%%%",
        base64.urlsafe_b64encode(b"not-json").decode(),
        base64.urlsafe_b64encode(json.dumps({"n": "missing-id"}).encode()).decode(),
    ]

    try:
        with TestClient(app) as client:
            for cursor in invalid_cursors:
                response = client.get("/api/v1/ingredients", params={"cursor": cursor})

                assert response.status_code == 422
                assert response.headers["content-type"].startswith("application/problem+json")
                assert response.json()["status"] == 422
                assert response.json()["code"] == "validation_error"
    finally:
        session.close()


def test_ingredient_route_filtered_cursor_preserves_filters(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    member = _member(session)
    prefix = f"filtered-{uuid4().hex}"
    matching = [_ingredient(member, f"{prefix}-{suffix}") for suffix in ("a", "b", "c")]
    excluded_global = _ingredient(member, f"{prefix}-global", global_ingredient=True)
    excluded_dimension = _ingredient(
        member,
        f"{prefix}-count",
        dimension=IngredientDimension.COUNT,
    )
    session.add_all([*matching, excluded_global, excluded_dimension])
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)
    expected_ids = {
        str(ingredient.id) for ingredient in sorted(matching, key=lambda item: item.normalized_name)
    }
    filters = {
        "query": prefix,
        "dimension": "mass",
        "include_global": False,
        "limit": 2,
    }

    try:
        with TestClient(app) as client:
            first_page = client.get("/api/v1/ingredients", params=filters)
            assert first_page.status_code == 200
            first_payload = first_page.json()
            assert first_payload["page_info"]["next_cursor"] is not None
            assert {item["id"] for item in first_payload["items"]}.issubset(expected_ids)

            second_page = client.get(
                "/api/v1/ingredients",
                params={
                    **filters,
                    "cursor": first_payload["page_info"]["next_cursor"],
                },
            )
            assert second_page.status_code == 200
            second_payload = second_page.json()

        actual_ids = {item["id"] for item in first_payload["items"] + second_payload["items"]}
        assert actual_ids == expected_ids
        assert len(first_payload["items"]) == 2
        assert len(second_payload["items"]) == 1
        assert second_payload["page_info"]["next_cursor"] is None
    finally:
        session.close()


def test_ingredient_route_filtered_cursor_returns_empty_final_page(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    member = _member(session)
    prefix = f"filtered-empty-{uuid4().hex}"
    matching = [_ingredient(member, f"{prefix}-{suffix}") for suffix in ("a", "b", "c")]
    session.add_all(matching)
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)
    filters = {"query": prefix, "dimension": "mass", "limit": 2}

    try:
        with TestClient(app) as client:
            first_page = client.get("/api/v1/ingredients", params=filters)
            assert first_page.status_code == 200
            cursor = first_page.json()["page_info"]["next_cursor"]
            assert cursor is not None

            remaining = next(
                ingredient
                for ingredient in matching
                if str(ingredient.id) not in {item["id"] for item in first_page.json()["items"]}
            )
            remaining.archived_at = datetime.now(UTC)
            session.commit()

            final_page = client.get(
                "/api/v1/ingredients",
                params={**filters, "cursor": cursor},
            )

        assert final_page.status_code == 200
        assert final_page.json()["items"] == []
        assert final_page.json()["page_info"] == {"next_cursor": None, "limit": 2}
    finally:
        session.close()


def test_ingredient_route_traverses_140_ingredients(
    integration_engine,
    monkeypatch,
) -> None:
    session = Session(integration_engine)
    member = _member(session)
    prefix = f"catalog-{uuid4().hex}"
    ingredients = [_ingredient(member, f"{prefix}-{index:03d}") for index in range(140)]
    session.add_all(ingredients)
    session.commit()
    monkeypatch.setitem(app.dependency_overrides, get_active_household_membership, lambda: member)

    try:
        with TestClient(app) as client:
            first_page = client.get(
                "/api/v1/ingredients",
                params={"query": prefix, "include_global": False, "limit": 100},
            )
            assert first_page.status_code == 200
            first_payload = first_page.json()
            assert len(first_payload["items"]) == 100
            assert first_payload["page_info"]["next_cursor"] is not None

            second_page = client.get(
                "/api/v1/ingredients",
                params={
                    "query": prefix,
                    "include_global": False,
                    "limit": 100,
                    "cursor": first_payload["page_info"]["next_cursor"],
                },
            )
            assert second_page.status_code == 200
            second_payload = second_page.json()

        actual_ids = [item["id"] for item in first_payload["items"] + second_payload["items"]]
        assert len(first_payload["items"]) == 100
        assert len(second_payload["items"]) == 40
        assert len(actual_ids) == len(set(actual_ids)) == 140
        assert set(actual_ids) == {str(ingredient.id) for ingredient in ingredients}
        assert second_payload["page_info"]["next_cursor"] is None
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
