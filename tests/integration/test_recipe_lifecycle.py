from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.api.plan_schemas import MealPlanCreate, MealPlanEntryCreate
from uribap_api.api.recipe_schemas import (
    RecipeCreate,
    RecipeRevision,
    RecipeUpdate,
    RecipeVersionCreate,
    RecipeVersionIngredientsPut,
    RecipeVersionIngredientUpsert,
)
from uribap_api.application.planning_service import add_entry, create_plan
from uribap_api.application.recipe_service import (
    _get_recipe_for_update,
    archive_recipe,
    create_recipe,
    create_version,
    list_published_versions,
    list_recipes,
    list_version_ingredients,
    publish_version,
    replace_version_ingredients,
    revise_recipe,
    unarchive_recipe,
    update_recipe,
)
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.recipes.policies import RecipeMealType, RecipeVersionState
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient
from uribap_api.infrastructure.persistence.recipe_models import Recipe, RecipeVersion

pytestmark = pytest.mark.integration


def _member(session: Session) -> HouseholdMember:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name="Lifecycle", locale="es", timezone="UTC"))
    member = HouseholdMember(
        household_id=household_id,
        user_id=user_id,
        role=MembershipRole.OWNER,
        status=MembershipStatus.ACTIVE,
    )
    session.add(member)
    session.commit()
    return member


def _ingredient(session: Session, member: HouseholdMember, name: str) -> Ingredient:
    ingredient = Ingredient(
        id=uuid4(),
        household_id=member.household_id,
        name=name,
        normalized_name=f"{name.casefold()}-{uuid4()}",
        dimension=IngredientDimension.MASS,
        base_unit="g",
        created_by_user_id=member.user_id,
    )
    session.add(ingredient)
    session.commit()
    return ingredient


def _line(ingredient: Ingredient, amount: str = "100") -> RecipeVersionIngredientUpsert:
    return RecipeVersionIngredientUpsert(
        ingredient_id=ingredient.id, amount=Decimal(amount), unit="g"
    )


def _recipe(session: Session, member: HouseholdMember, name: str | None = None):
    return create_recipe(
        session,
        member,
        RecipeCreate(name=name or f"Recipe {uuid4()}", base_servings=2, prep_minutes=10),
    )


def _member_snapshot(member: HouseholdMember) -> HouseholdMember:
    return HouseholdMember(
        id=member.id,
        household_id=member.household_id,
        user_id=member.user_id,
        role=member.role,
        status=member.status,
    )


def test_update_recipe_normalizes_name_and_clears_description(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        recipe = _recipe(session, member)
        recipe.description = "Old description"
        session.commit()

        updated = update_recipe(
            session,
            member,
            recipe.id,
            RecipeUpdate.model_validate({"name": "  New   Recipe Name ", "description": None}),
        )

        assert updated.name == "New Recipe Name"
        assert updated.normalized_name == "new recipe name"
        assert updated.description is None


def test_revise_published_recipe_clones_lines_and_publishes_new_version(
    integration_engine,
) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        rice = _ingredient(session, member, "Rice")
        recipe = _recipe(session, member)
        replace = RecipeRevision(items=[_line(rice, "250")], publish=False)
        draft = revise_recipe(session, member, recipe.id, replace)
        first = publish_version(session, member, recipe.id, draft.version_number)
        first_line = list_version_ingredients(session, first)[0]

        revised = revise_recipe(
            session,
            member,
            recipe.id,
            RecipeRevision(base_servings=4, prep_minutes=25),
        )

        assert revised.version_number == 2
        assert revised.state == RecipeVersionState.PUBLISHED
        assert revised.base_servings == 4
        assert revised.prep_minutes == 25
        assert first.state == RecipeVersionState.ARCHIVED
        assert first_line.amount == Decimal("250")
        cloned = list_version_ingredients(session, revised)
        assert len(cloned) == 1
        assert cloned[0].id != first_line.id
        assert cloned[0].ingredient_id == first_line.ingredient_id
        assert cloned[0].amount == first_line.amount
        assert cloned[0].unit == first_line.unit
        assert cloned[0].optional == first_line.optional
        assert cloned[0].position == first_line.position


def test_revise_latest_draft_edits_in_place_and_replaces_lines(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        rice = _ingredient(session, member, "Rice")
        salt = _ingredient(session, member, "Salt")
        recipe = _recipe(session, member)
        draft = revise_recipe(
            session, member, recipe.id, RecipeRevision(items=[_line(rice)], publish=False)
        )

        edited = revise_recipe(
            session,
            member,
            recipe.id,
            RecipeRevision(
                base_servings=5,
                items=[_line(salt, "8")],
                publish=False,
            ),
        )

        versions = list(
            session.scalars(
                select(RecipeVersion).where(RecipeVersion.recipe_id == recipe.id)
            )
        )
        lines = list_version_ingredients(session, edited)
        assert edited.id == draft.id
        assert edited.version_number == 1
        assert edited.base_servings == 5
        assert edited.state == RecipeVersionState.DRAFT
        assert len(versions) == 1
        assert len(lines) == 1
        assert lines[0].ingredient_id == salt.id
        assert lines[0].amount == Decimal("8")


def test_publish_version_archives_the_previous_published_version(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        recipe = _recipe(session, member)
        first = publish_version(session, member, recipe.id, 1)
        second = create_version(session, member, recipe.id, RecipeVersionCreate())

        published = publish_version(session, member, recipe.id, second.version_number)

        assert published.state == RecipeVersionState.PUBLISHED
        assert first.state == RecipeVersionState.ARCHIVED
        assert len(list_published_versions(session, member)) == 1


def test_archive_and_unarchive_are_idempotent(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        recipe = _recipe(session, member)

        archived = archive_recipe(session, member, recipe.id)
        first_timestamp = archived.archived_at
        archived_again = archive_recipe(session, member, recipe.id)
        assert archived_again.archived_at == first_timestamp

        unarchived = unarchive_recipe(session, member, recipe.id)
        unarchived_again = unarchive_recipe(session, member, recipe.id)

        assert first_timestamp is not None
        assert unarchived.archived_at is None
        assert unarchived_again.archived_at is None


def test_archived_recipe_cannot_be_updated_or_revised_and_is_hidden(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        recipe = _recipe(session, member)
        publish_version(session, member, recipe.id, 1)
        archive_recipe(session, member, recipe.id)

        with pytest.raises(DomainError) as update_error:
            update_recipe(session, member, recipe.id, RecipeUpdate(name="Changed"))
        with pytest.raises(DomainError) as revise_error:
            revise_recipe(session, member, recipe.id, RecipeRevision())

        assert update_error.value.status_code == 409
        assert update_error.value.title == "Recipe archived"
        assert revise_error.value.status_code == 409
        assert revise_error.value.title == "Recipe archived"
        assert all(
            row.id != recipe.id
            for row, _version in list_recipes(session, member, None, False, 50)
        )
        assert list_published_versions(session, member) == []


@pytest.mark.parametrize(
    "operation", ["create_version", "replace_version_ingredients", "publish_version"]
)
def test_archived_recipe_rejects_all_version_writes(integration_engine, operation: str) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        recipe = _recipe(session, member)
        archive_recipe(session, member, recipe.id)

        with pytest.raises(DomainError) as excinfo:
            if operation == "create_version":
                create_version(session, member, recipe.id, RecipeVersionCreate())
            elif operation == "replace_version_ingredients":
                replace_version_ingredients(
                    session,
                    member,
                    recipe.id,
                    1,
                    RecipeVersionIngredientsPut(items=[]),
                )
            else:
                publish_version(session, member, recipe.id, 1)

        assert excinfo.value.status_code == 409
        assert excinfo.value.title == "Recipe archived"


def test_publish_and_replace_lock_recipe_before_version_writes(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        publish_recipe = _recipe(session, member)
        replace_recipe = _recipe(session, member)
        member_snapshot = _member_snapshot(member)
        publish_recipe_id = publish_recipe.id
        replace_recipe_id = replace_recipe.id

    def blocks_on_recipe_lock(recipe_id, operation) -> bool:
        with integration_engine.connect() as lock_connection:
            lock_connection.execute(
                select(Recipe.id).where(Recipe.id == recipe_id).with_for_update()
            )
            finished = Event()
            failures: list[BaseException] = []

            def run_operation() -> None:
                try:
                    with Session(integration_engine) as worker_session:
                        operation(worker_session)
                except BaseException as exc:
                    failures.append(exc)
                finally:
                    finished.set()

            worker = Thread(target=run_operation, daemon=True)
            worker.start()
            try:
                was_blocked = not finished.wait(timeout=1)
            finally:
                lock_connection.commit()
            worker.join(timeout=10)

        assert not worker.is_alive()
        assert not failures
        return was_blocked

    publish_blocked = blocks_on_recipe_lock(
        publish_recipe_id,
        lambda session: publish_version(session, member_snapshot, publish_recipe_id, 1),
    )
    replace_blocked = blocks_on_recipe_lock(
        replace_recipe_id,
        lambda session: replace_version_ingredients(
            session,
            member_snapshot,
            replace_recipe_id,
            1,
            RecipeVersionIngredientsPut(items=[]),
        ),
    )

    assert publish_blocked
    assert replace_blocked


def test_update_recipe_waits_for_archive_and_rejects_after_lock_release(integration_engine):
    with Session(integration_engine) as session:
        member = _member(session)
        recipe = _recipe(session, member)
        member_snapshot = _member_snapshot(member)
        recipe_id = recipe.id

    started = Event()
    finished = Event()
    outcomes: list[Recipe | BaseException] = []

    def run_update() -> None:
        started.set()
        try:
            with Session(integration_engine) as worker_session:
                outcomes.append(
                    update_recipe(
                        worker_session,
                        member_snapshot,
                        recipe_id,
                        RecipeUpdate(name="Updated"),
                    )
                )
        except BaseException as exc:
            outcomes.append(exc)
        finally:
            finished.set()

    with Session(integration_engine) as archive_session:
        locked_recipe = _get_recipe_for_update(archive_session, member_snapshot, recipe_id)
        locked_recipe.archived_at = datetime.now(UTC)
        worker = Thread(target=run_update, daemon=True)
        worker.start()
        worker_started = started.wait(timeout=5)
        update_blocked = worker_started and not finished.wait(timeout=0.5)
        archive_session.commit()
        worker.join(timeout=10)

    assert worker_started
    assert update_blocked
    assert not worker.is_alive()
    assert len(outcomes) == 1
    assert isinstance(outcomes[0], DomainError)
    assert outcomes[0].status_code == 409


def test_concurrent_create_version_calls_use_distinct_numbers(integration_engine):
    with Session(integration_engine) as session:
        member = _member(session)
        recipe = _recipe(session, member)
        member_snapshot = _member_snapshot(member)
        recipe_id = recipe.id

    started = [Event(), Event()]
    any_finished = Event()
    outcomes: list[RecipeVersion | BaseException | None] = [None, None]

    def run_create_version(index: int) -> None:
        started[index].set()
        try:
            with Session(integration_engine) as worker_session:
                outcomes[index] = create_version(
                    worker_session,
                    member_snapshot,
                    recipe_id,
                    RecipeVersionCreate(base_servings=2, prep_minutes=15),
                )
        except BaseException as exc:
            outcomes[index] = exc
        finally:
            any_finished.set()

    with Session(integration_engine) as lock_session:
        _get_recipe_for_update(lock_session, member_snapshot, recipe_id)
        workers = [
            Thread(target=run_create_version, args=(index,), daemon=True)
            for index in range(2)
        ]
        for worker in workers:
            worker.start()
        workers_started = all(event.wait(timeout=5) for event in started)
        writes_blocked = workers_started and not any_finished.wait(timeout=0.5)
        lock_session.commit()
        for worker in workers:
            worker.join(timeout=10)

    assert workers_started
    assert writes_blocked
    assert all(not worker.is_alive() for worker in workers)
    assert all(isinstance(outcome, RecipeVersion) for outcome in outcomes), outcomes
    version_numbers = sorted(
        outcome.version_number
        for outcome in outcomes
        if isinstance(outcome, RecipeVersion)
    )
    assert version_numbers == [2, 3]


def test_archived_recipe_version_cannot_be_added_to_a_plan(integration_engine) -> None:
    with Session(integration_engine) as session:
        member = _member(session)
        recipe = _recipe(session, member)
        version = publish_version(session, member, recipe.id, 1)
        archive_recipe(session, member, recipe.id)
        planned_date = date(2026, 10, 5) + timedelta(weeks=int(uuid4().int % 1000))
        plan = create_plan(session, member, MealPlanCreate(week_start_date=planned_date), None)

        with pytest.raises(DomainError) as excinfo:
            add_entry(
                session,
                member,
                plan.payload["id"],
                MealPlanEntryCreate(
                    expected_version=plan.payload["version"],
                    planned_date=planned_date,
                    meal_type=RecipeMealType.DINNER,
                    recipe_version_id=version.id,
                    servings=2,
                ),
                None,
            )

        assert excinfo.value.status_code == 422
        assert excinfo.value.title == "Recipe archived"


def test_recipe_lifecycle_operations_enforce_tenant_isolation(integration_engine) -> None:
    with Session(integration_engine) as session:
        owner = _member(session)
        other_member = _member(session)
        recipe = _recipe(session, owner)

        with pytest.raises(DomainError) as update_error:
            update_recipe(session, other_member, recipe.id, RecipeUpdate(name="Hidden"))
        with pytest.raises(DomainError) as revise_error:
            revise_recipe(session, other_member, recipe.id, RecipeRevision())
        with pytest.raises(DomainError) as archive_error:
            archive_recipe(session, other_member, recipe.id)

        assert update_error.value.status_code == 404
        assert revise_error.value.status_code == 404
        assert archive_error.value.status_code == 404
