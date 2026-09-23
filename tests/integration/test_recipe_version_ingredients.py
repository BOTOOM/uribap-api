from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from uribap_api.api.recipe_schemas import (
    RecipeCreate,
    RecipeVersionCreate,
    RecipeVersionIngredientsPut,
    RecipeVersionIngredientUpsert,
)
from uribap_api.application.recipe_service import (
    create_recipe,
    create_version,
    get_version,
    list_recipes,
    list_version_ingredients,
    publish_version,
    replace_version_ingredients,
)
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient

pytestmark = pytest.mark.integration


def _member(session: Session) -> HouseholdMember:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="HH", locale="es", timezone="UTC"))
    member = HouseholdMember(
        household_id=household_id,
        user_id=user_id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(member)
    session.commit()
    return member


def _ingredient(
    session: Session, member: HouseholdMember, name: str, dimension=IngredientDimension.MASS
) -> Ingredient:
    ingredient = Ingredient(
        id=uuid4(),
        household_id=member.household_id,
        name=name,
        normalized_name=f"{name}-{uuid4()}",
        dimension=dimension,
        base_unit="g",
    )
    session.add(ingredient)
    session.commit()
    return ingredient


def _draft_version(session: Session, member: HouseholdMember):
    recipe = create_recipe(session, member, RecipeCreate(name=f"R {uuid4()}", base_servings=4))
    return recipe, get_version(session, member, recipe.id, 1)


def test_replace_version_ingredients_writes_lines_in_position_order(
    integration_engine,
) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        rice = _ingredient(session, member, "Rice")
        chicken = _ingredient(session, member, "Chicken")
        recipe, version = _draft_version(session, member)

        lines = replace_version_ingredients(
            session,
            member,
            recipe.id,
            version.version_number,
            RecipeVersionIngredientsPut(
                items=[
                    RecipeVersionIngredientUpsert(
                        ingredient_id=chicken.id, amount=Decimal("800"), unit="g"
                    ),
                    RecipeVersionIngredientUpsert(
                        ingredient_id=rice.id, amount=Decimal("300"), unit="g", optional=True
                    ),
                ]
            ),
        )

        assert [line.ingredient_id for line in lines] == [chicken.id, rice.id]
        assert [line.position for line in lines] == [0, 1]
        assert lines[1].optional is True

        stored = list_version_ingredients(session, version)
        assert len(stored) == 2


def test_replace_version_ingredients_replaces_existing_lines(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        rice = _ingredient(session, member, "Rice")
        oil = _ingredient(session, member, "Oil")
        recipe, version = _draft_version(session, member)

        replace_version_ingredients(
            session,
            member,
            recipe.id,
            1,
            RecipeVersionIngredientsPut(
                items=[
                    RecipeVersionIngredientUpsert(
                        ingredient_id=rice.id, amount=Decimal("1"), unit="kg"
                    )
                ]
            ),
        )
        replace_version_ingredients(
            session,
            member,
            recipe.id,
            1,
            RecipeVersionIngredientsPut(
                items=[
                    RecipeVersionIngredientUpsert(
                        ingredient_id=oil.id, amount=Decimal("50"), unit="g"
                    )
                ]
            ),
        )

        stored = list_version_ingredients(session, version)
        assert len(stored) == 1
        assert stored[0].ingredient_id == oil.id


def test_replace_version_ingredients_rejects_wrong_unit_dimension(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        rice = _ingredient(session, member, "Rice")
        recipe, _version = _draft_version(session, member)

        with pytest.raises(DomainError) as excinfo:
            replace_version_ingredients(
                session,
                member,
                recipe.id,
                1,
                RecipeVersionIngredientsPut(
                    items=[
                        RecipeVersionIngredientUpsert(
                            ingredient_id=rice.id, amount=Decimal("1"), unit="ml"
                        )
                    ]
                ),
            )
        assert excinfo.value.status_code == 422


def test_replace_version_ingredients_rejects_foreign_ingredient(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        other_member = _member(session)
        foreign = _ingredient(session, other_member, "Foreign rice")
        recipe, _version = _draft_version(session, member)

        with pytest.raises(DomainError) as excinfo:
            replace_version_ingredients(
                session,
                member,
                recipe.id,
                1,
                RecipeVersionIngredientsPut(
                    items=[
                        RecipeVersionIngredientUpsert(
                            ingredient_id=foreign.id, amount=Decimal("1"), unit="kg"
                        )
                    ]
                ),
            )
        assert excinfo.value.status_code == 404


def test_replace_version_ingredients_rejects_published_version(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        rice = _ingredient(session, member, "Rice")
        recipe, version = _draft_version(session, member)
        publish_version(session, member, recipe.id, version.version_number)

        with pytest.raises(DomainError) as excinfo:
            replace_version_ingredients(
                session,
                member,
                recipe.id,
                1,
                RecipeVersionIngredientsPut(
                    items=[
                        RecipeVersionIngredientUpsert(
                            ingredient_id=rice.id, amount=Decimal("1"), unit="kg"
                        )
                    ]
                ),
            )
        assert excinfo.value.status_code == 409


def test_list_recipes_returns_latest_version_per_recipe(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        recipe, version = _draft_version(session, member)
        publish_version(session, member, recipe.id, version.version_number)
        create_version(
            session, member, recipe.id, RecipeVersionCreate(base_servings=2, prep_minutes=15)
        )
        other, _ = _draft_version(session, member)

        rows = list_recipes(session, member, query=None, archived=False, limit=50)

        latest_by_recipe = {item.id: latest for item, latest in rows}
        recipe_latest = latest_by_recipe[recipe.id]
        other_latest = latest_by_recipe[other.id]
        assert recipe_latest is not None and other_latest is not None
        assert recipe_latest.version_number == 2
        assert other_latest.version_number == 1
