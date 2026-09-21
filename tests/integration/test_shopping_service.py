from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from uribap_api.api.plan_schemas import (
    MealPlanCreate,
    MealPlanEntryCreate,
    MealPlanTransition,
)
from uribap_api.api.shopping_schemas import (
    ShoppingListCreate,
    ShoppingPurchase,
)
from uribap_api.application.forecast_service import demand_forecast
from uribap_api.application.planning_service import add_entry, create_plan, transition_plan
from uribap_api.application.shopping_service import (
    create_shopping_list,
    get_current_list,
    get_shopping_list,
    purchase_item,
    transition_item,
    transition_list,
)
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.inventory.ledger import InventoryLocation, InventoryMovementType
from uribap_api.domain.planning.policies import MealPlanAction
from uribap_api.domain.recipes.policies import RecipeMealType, RecipeVersionState
from uribap_api.domain.shared.errors import DomainError
from uribap_api.domain.shopping.policies import (
    ShoppingItemAction,
    ShoppingListAction,
)
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.inventory_models import (
    InventoryLot,
    InventoryMovement,
)
from uribap_api.infrastructure.persistence.recipe_models import (
    Recipe,
    RecipeVersion,
    RecipeVersionIngredient,
)
from uribap_api.infrastructure.persistence.shopping_models import ShoppingItem

WEEK = date(2027, 2, 1) + timedelta(weeks=int(uuid4().int % 300))


def _member(session: Session) -> tuple[Household, HouseholdMember]:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="Sh", locale="es", timezone="UTC"))
    member = HouseholdMember(
        household_id=household_id,
        user_id=user_id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(member)
    session.flush()
    household = session.get(Household, household_id)
    assert household is not None
    return household, member


def _ingredient(session: Session, household: Household, name: str) -> Ingredient:
    ingredient = Ingredient(
        id=uuid4(),
        household_id=household.id,
        name=name,
        normalized_name=f"{name}-{uuid4()}",
        dimension=IngredientDimension.MASS,
        base_unit="g",
    )
    session.add(ingredient)
    session.flush()
    return ingredient


def _version(
    session: Session,
    household: Household,
    member: HouseholdMember,
    ingredient: Ingredient,
    amount: str,
    unit: str = "g",
    base: int = 2,
) -> RecipeVersion:
    recipe = Recipe(
        id=uuid4(),
        household_id=household.id,
        name=f"Recipe {uuid4()}",
        normalized_name=str(uuid4()),
        created_by_user_id=member.user_id,
    )
    version = RecipeVersion(
        id=uuid4(),
        recipe_id=recipe.id,
        version_number=1,
        base_servings=base,
        prep_minutes=10,
        state=RecipeVersionState.PUBLISHED,
        created_by_user_id=member.user_id,
        published_by_user_id=member.user_id,
    )
    line = RecipeVersionIngredient(
        recipe_version_id=version.id,
        ingredient_id=ingredient.id,
        amount=Decimal(amount),
        unit=unit,
        position=0,
    )
    session.add_all([recipe, version, line])
    session.flush()
    return version


def _approved_plan(
    session: Session,
    member: HouseholdMember,
    week: date,
    entries: list[tuple[date, RecipeVersion, int]],
) -> str:
    plan = create_plan(session, member, MealPlanCreate(week_start_date=week), None)
    plan_id = plan.payload["id"]
    version = plan.payload["version"]
    for position, (day, recipe_version, servings) in enumerate(entries):
        result = add_entry(
            session,
            member,
            plan_id,
            MealPlanEntryCreate(
                expected_version=version,
                planned_date=day,
                meal_type=RecipeMealType.DINNER,
                recipe_version_id=recipe_version.id,
                servings=servings,
                position=position,
            ),
            None,
        )
        version = result.payload["version"]
    transition_plan(
        session,
        member,
        plan_id,
        MealPlanAction.PROPOSE,
        MealPlanTransition(expected_version=version),
        None,
    )
    version += 1
    transition_plan(
        session,
        member,
        plan_id,
        MealPlanAction.APPROVE,
        MealPlanTransition(expected_version=version),
        None,
    )
    return plan_id


def _lot(
    session: Session,
    household: Household,
    member: HouseholdMember,
    ingredient: Ingredient,
    amount: str,
    expires: date | None = None,
) -> None:
    session.add(
        InventoryLot(
            household_id=household.id,
            ingredient_id=ingredient.id,
            quantity_on_hand=Decimal(amount),
            unit="g",
            location=InventoryLocation.PANTRY,
            available=True,
            expiration_date=expires,
            created_by_user_id=member.user_id,
        )
    )
    session.flush()


def _new_list(session: Session, member: HouseholdMember, from_date: date, days: int = 6) -> dict:
    return create_shopping_list(
        session,
        member,
        ShoppingListCreate(from_date=from_date, to_date=from_date + timedelta(days=days)),
        None,
    ).payload


def _list_id(payload: dict) -> UUID:
    return UUID(payload["id"])


def _item_ids(payload: dict) -> list[UUID]:
    return [UUID(item["id"]) for item in payload["items"]]


@pytest.mark.integration
def test_create_list_projects_shortfall_items(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 1600)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "ShopRice")
        oil = _ingredient(session, household, "ShopOil")
        rice_v = _version(session, household, member, rice, "100", base=2)
        oil_v = _version(session, household, member, oil, "10", base=2)
        _lot(session, household, member, rice, "50", expires=week + timedelta(days=30))
        _lot(session, household, member, oil, "50", expires=week + timedelta(days=30))
        session.commit()
        _approved_plan(
            session, member, week, [(week, rice_v, 4), (week + timedelta(days=1), oil_v, 2)]
        )
        session.commit()

        result = _new_list(session, member, week)
        # rice: demand 200, on hand 50 -> shortfall 150; oil: demand 10, on hand 50 -> no item.
        assert result["state"] == "open"
        assert result["version"] == 1
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["ingredient_id"] == str(rice.id)
        assert item["ingredient_name"] == "ShopRice"
        assert item["needed_amount"] == "150.000000"
        assert item["status"] == "pending"
        assert item["position"] == 0
        current = get_current_list(session, member)
        assert current.id == _list_id(result)


@pytest.mark.integration
def test_create_list_empty_without_shortfall_and_window_conflict(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 1900)
    with Session(integration_engine) as session:
        household, member = _member(session)
        result = _new_list(session, member, week)
        assert result["items"] == []

        with pytest.raises(DomainError) as exc:
            _new_list(session, member, week)
        assert exc.value.status_code == 409

        transition_list(session, member, _list_id(result), ShoppingListAction.ARCHIVE, 1, None)
        archived = _new_list(session, member, week)
        assert archived["state"] == "open"
        assert archived["id"] != result["id"]


@pytest.mark.integration
def test_item_skip_restore_and_version_conflict(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 2200)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "SkipRice")
        rice_v = _version(session, household, member, rice, "100", base=2)
        session.commit()
        _approved_plan(session, member, week, [(week, rice_v, 4)])
        session.commit()
        payload = _new_list(session, member, week)
        item_id = _item_ids(payload)[0]

        with pytest.raises(DomainError) as exc:
            transition_item(
                session, member, _list_id(payload), item_id, ShoppingItemAction.SKIP, 99, None
            )
        assert exc.value.status_code == 409
        skipped = transition_item(
            session, member, _list_id(payload), item_id, ShoppingItemAction.SKIP, 1, None
        ).payload
        assert skipped["items"][0]["status"] == "skipped"
        assert skipped["version"] == 2
        with pytest.raises(DomainError) as exc:
            transition_item(
                session, member, _list_id(payload), item_id, ShoppingItemAction.SKIP, 2, None
            )
        assert exc.value.status_code == 409
        restored = transition_item(
            session, member, _list_id(payload), item_id, ShoppingItemAction.RESTORE, 2, None
        ).payload
        assert restored["items"][0]["status"] == "pending"
        assert restored["version"] == 3


@pytest.mark.integration
def test_purchase_creates_lot_movement_and_marks_item(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 2500)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "BuyRice")
        rice_v = _version(session, household, member, rice, "100", base=2)
        session.commit()
        _approved_plan(session, member, week, [(week, rice_v, 4)])
        session.commit()
        payload = _new_list(session, member, week)
        item_id = _item_ids(payload)[0]

        with pytest.raises(DomainError) as exc:
            purchase_item(
                session,
                member,
                _list_id(payload),
                item_id,
                ShoppingPurchase(
                    expected_version=1,
                    quantity=Decimal("2"),
                    unit="kg",
                    location=InventoryLocation.PANTRY,
                ),
                None,
            )
        assert exc.value.status_code == 422

        result = purchase_item(
            session,
            member,
            _list_id(payload),
            item_id,
            ShoppingPurchase(
                expected_version=1,
                quantity=Decimal("180"),
                unit="g",
                location=InventoryLocation.REFRIGERATOR,
                expiration_date=week + timedelta(days=10),
            ),
            None,
        ).payload
        item = result["items"][0]
        assert item["status"] == "purchased"
        assert item["purchased_amount"] == "180.000000"
        assert item["purchased_lot_id"] is not None
        assert result["version"] == 2

        lot = session.get(InventoryLot, UUID(item["purchased_lot_id"]))
        assert lot is not None
        assert lot.household_id == household.id
        assert lot.quantity_on_hand == Decimal("180.000000")
        assert lot.location == InventoryLocation.REFRIGERATOR
        movement = session.scalar(
            select(InventoryMovement).where(
                InventoryMovement.lot_id == lot.id,
                InventoryMovement.source_type == "shopping_item",
            )
        )
        assert movement is not None
        assert movement.movement_type == InventoryMovementType.PURCHASE
        assert movement.source_id == item_id

        # the new lot feeds the next projection's on-hand total
        forecast = demand_forecast(session, member, week, week + timedelta(days=6))
        line = forecast.items[0]
        assert line.on_hand_amount == Decimal("180.000000")
        assert line.shortfall_amount == Decimal("20.000000")

        # a purchased item cannot be purchased again
        with pytest.raises(DomainError) as exc:
            purchase_item(
                session,
                member,
                _list_id(payload),
                item_id,
                ShoppingPurchase(
                    expected_version=2,
                    quantity=Decimal("1"),
                    unit="g",
                    location=InventoryLocation.PANTRY,
                ),
                None,
            )
        assert exc.value.status_code == 409


@pytest.mark.integration
def test_purchase_idempotent_replay_and_key_conflict(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 2800)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "IdemRice")
        rice_v = _version(session, household, member, rice, "100", base=2)
        session.commit()
        _approved_plan(session, member, week, [(week, rice_v, 4)])
        session.commit()
        payload = _new_list(session, member, week)
        item_id = _item_ids(payload)[0]
        request = ShoppingPurchase(
            expected_version=1,
            quantity=Decimal("200"),
            unit="g",
            location=InventoryLocation.PANTRY,
        )

        first = purchase_item(
            session, member, _list_id(payload), item_id, request, "purchase-key-1"
        ).payload
        replay = purchase_item(
            session, member, _list_id(payload), item_id, request, "purchase-key-1"
        ).payload
        assert replay == first

        lots = session.scalar(
            select(func.count())
            .select_from(InventoryLot)
            .where(InventoryLot.household_id == household.id)
        )
        assert lots == 1

        with pytest.raises(DomainError) as exc:
            purchase_item(
                session,
                member,
                _list_id(payload),
                item_id,
                ShoppingPurchase(
                    expected_version=1,
                    quantity=Decimal("50"),
                    unit="g",
                    location=InventoryLocation.PANTRY,
                ),
                "purchase-key-1",
            )
        assert exc.value.status_code == 409


@pytest.mark.integration
def test_complete_reopen_archive_flow(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 3100)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "FlowRice")
        rice_v = _version(session, household, member, rice, "100", base=2)
        session.commit()
        _approved_plan(session, member, week, [(week, rice_v, 4)])
        session.commit()
        payload = _new_list(session, member, week)
        item_id = _item_ids(payload)[0]

        with pytest.raises(DomainError) as exc:
            transition_list(
                session, member, _list_id(payload), ShoppingListAction.COMPLETE, 1, None
            )
        assert exc.value.status_code == 409

        purchase_item(
            session,
            member,
            _list_id(payload),
            item_id,
            ShoppingPurchase(
                expected_version=1,
                quantity=Decimal("200"),
                unit="g",
                location=InventoryLocation.PANTRY,
            ),
            None,
        )
        completed = transition_list(
            session, member, _list_id(payload), ShoppingListAction.COMPLETE, 2, None
        ).payload
        assert completed["state"] == "completed"
        assert completed["version"] == 3

        # items are immutable while the list is not open
        with pytest.raises(DomainError) as exc:
            transition_item(
                session,
                member,
                _list_id(payload),
                item_id,
                ShoppingItemAction.SKIP,
                3,
                None,
            )
        assert exc.value.status_code == 409

        reopened = transition_list(
            session, member, _list_id(payload), ShoppingListAction.REOPEN, 3, None
        ).payload
        assert reopened["state"] == "open"
        archived = transition_list(
            session, member, _list_id(payload), ShoppingListAction.ARCHIVE, 4, None
        ).payload
        assert archived["state"] == "archived"
        with pytest.raises(DomainError) as exc:
            transition_list(session, member, _list_id(payload), ShoppingListAction.REOPEN, 5, None)
        assert exc.value.status_code == 409
        with pytest.raises(DomainError) as exc:
            get_current_list(session, member)
        assert exc.value.status_code == 404


@pytest.mark.integration
def test_shopping_tenant_isolation(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 3400)
    with Session(integration_engine) as session:
        household, member = _member(session)
        _other_household, outsider = _member(session)
        rice = _ingredient(session, household, "TenantRice")
        rice_v = _version(session, household, member, rice, "100", base=2)
        session.commit()
        _approved_plan(session, member, week, [(week, rice_v, 4)])
        session.commit()
        payload = _new_list(session, member, week)
        item_id = _item_ids(payload)[0]

        with pytest.raises(DomainError) as exc:
            get_shopping_list(session, outsider, _list_id(payload))
        assert exc.value.status_code == 404
        with pytest.raises(DomainError) as exc:
            purchase_item(
                session,
                outsider,
                _list_id(payload),
                item_id,
                ShoppingPurchase(
                    expected_version=1,
                    quantity=Decimal("1"),
                    unit="g",
                    location=InventoryLocation.PANTRY,
                ),
                None,
            )
        assert exc.value.status_code == 404
        with pytest.raises(DomainError) as exc:
            get_current_list(session, outsider)
        assert exc.value.status_code == 404


@pytest.mark.integration
def test_shopping_does_not_mutate_plans(integration_engine) -> None:
    week = WEEK + timedelta(weeks=int(uuid4().int % 200) + 3700)
    with Session(integration_engine) as session:
        household, member = _member(session)
        rice = _ingredient(session, household, "SafeRice")
        rice_v = _version(session, household, member, rice, "100", base=2)
        session.commit()
        _approved_plan(session, member, week, [(week, rice_v, 4)])
        session.commit()
        payload = _new_list(session, member, week)
        item_id = _item_ids(payload)[0]
        purchase_item(
            session,
            member,
            _list_id(payload),
            item_id,
            ShoppingPurchase(
                expected_version=1,
                quantity=Decimal("200"),
                unit="g",
                location=InventoryLocation.PANTRY,
            ),
            None,
        )

        items = session.scalar(
            select(func.count())
            .select_from(ShoppingItem)
            .where(ShoppingItem.household_id == household.id)
        )
        assert items == 1
        forecast = demand_forecast(session, member, week, week + timedelta(days=6))
        assert forecast.items[0].shortfall_amount == Decimal("0.000000")
