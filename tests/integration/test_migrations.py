from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, select, text, update
from sqlalchemy.orm import Session

from uribap_api.api.completion_schemas import (
    MealCompletionCreate,
    MealCompletionResponse,
)
from uribap_api.application.completion_service import (
    complete_entry,
    correct_line,
    reopen_completion,
)
from uribap_api.domain.completion.policies import MealCompletionOutcome, MealCompletionState
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.ingredients.policies import IngredientDimension
from uribap_api.domain.shared.fingerprint import operation_fingerprint
from uribap_api.infrastructure.persistence.completion_models import (
    CompletionOperation,
    MealCompletion,
)
from uribap_api.infrastructure.persistence.household_models import Household, HouseholdMember
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.infrastructure.persistence.ingredient_models import Ingredient


def _legacy_completion_payload(
    *,
    completion_id: UUID,
    entry_id: UUID,
    user_id: UUID,
    state: MealCompletionState,
    version: int,
) -> dict[str, object]:
    now = datetime.now(UTC)
    payload = MealCompletionResponse(
        id=completion_id,
        state=state,
        outcome=MealCompletionOutcome.COOKED,
        outcome_note=None,
        version=version,
        meal_plan_entry_id=entry_id,
        planned_date=None,
        meal_type=None,
        recipe_version_id=None,
        recipe_name=None,
        lines=[],
        completed_by_user_id=user_id,
        completed_at=now,
        reopened_by_user_id=user_id if state == MealCompletionState.REOPENED else None,
        reopened_at=now if state == MealCompletionState.REOPENED else None,
        reopen_reason="legacy reopen" if state == MealCompletionState.REOPENED else None,
        created_at=now,
        updated_at=now,
    ).model_dump(mode="json")
    del payload["outcome"]
    del payload["outcome_note"]
    return payload


@pytest.mark.integration
def test_current_migration_head_is_applied(integration_engine: Engine) -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = scripts.get_heads()
    assert len(heads) == 1

    with integration_engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == heads[0]


@pytest.mark.integration
def test_pantry_staple_migration_defaults_existing_ingredients_to_false(
    integration_engine: Engine,
) -> None:
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(config_path))
    user_id, household_id, ingredient_id = uuid4(), uuid4(), uuid4()
    with Session(integration_engine) as session:
        session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
        session.add(
            Household(id=household_id, name="Pantry migration", locale="es", timezone="UTC")
        )
        session.add(
            Ingredient(
                id=ingredient_id,
                household_id=household_id,
                name="Pantry migration salt",
                normalized_name=f"pantry-migration-{uuid4()}",
                dimension=IngredientDimension.MASS,
                base_unit="g",
                created_by_user_id=user_id,
            )
        )
        session.commit()
        session.execute(
            text("UPDATE ingredient SET pantry_staple = true WHERE id = :ingredient_id"),
            {"ingredient_id": ingredient_id},
        )
        session.commit()

    try:
        command.downgrade(config, "6b1354a22e91")
        command.upgrade(config, "head")
        with integration_engine.connect() as connection:
            pantry_staple = connection.execute(
                text("SELECT pantry_staple FROM ingredient WHERE id = :ingredient_id"),
                {"ingredient_id": ingredient_id},
            ).scalar_one()
        assert pantry_staple is False
    finally:
        command.upgrade(config, "head")
        with Session(integration_engine) as session:
            session.execute(
                text("DELETE FROM ingredient WHERE id = :ingredient_id"),
                {"ingredient_id": ingredient_id},
            )
            session.execute(
                text("DELETE FROM household WHERE id = :household_id"),
                {"household_id": household_id},
            )
            session.execute(text("DELETE FROM app_user WHERE id = :user_id"), {"user_id": user_id})
            session.commit()


@pytest.mark.integration
def test_legacy_completion_receipts_are_backfilled_and_replayable(
    integration_engine: Engine,
) -> None:
    config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(config_path))
    household_id, user_id = uuid4(), uuid4()
    plan_id, entry_id, completion_id, line_id = uuid4(), uuid4(), uuid4(), uuid4()
    receipt_keys = {
        "meal_entry_complete": "legacy-complete",
        "meal_completion_line_correct": "legacy-correct",
        "meal_completion_reopen": "legacy-reopen",
    }
    operations = [
        (
            "meal_entry_complete",
            receipt_keys["meal_entry_complete"],
            operation_fingerprint(
                "meal_entry_complete",
                {"plan_id": str(plan_id), "entry_id": str(entry_id), "lines": None},
            ),
            _legacy_completion_payload(
                completion_id=completion_id,
                entry_id=entry_id,
                user_id=user_id,
                state=MealCompletionState.RECORDED,
                version=1,
            ),
        ),
        (
            "meal_completion_line_correct",
            receipt_keys["meal_completion_line_correct"],
            operation_fingerprint(
                "meal_completion_line_correct",
                {
                    "completion_id": str(completion_id),
                    "line_id": str(line_id),
                    "expected_version": 1,
                    "actual_amount": "0.5",
                    "unit": "g",
                },
            ),
            _legacy_completion_payload(
                completion_id=completion_id,
                entry_id=entry_id,
                user_id=user_id,
                state=MealCompletionState.RECORDED,
                version=2,
            ),
        ),
        (
            "meal_completion_reopen",
            receipt_keys["meal_completion_reopen"],
            operation_fingerprint(
                "meal_completion_reopen",
                {
                    "completion_id": str(completion_id),
                    "expected_version": 2,
                    "reason": "legacy reopen",
                },
            ),
            _legacy_completion_payload(
                completion_id=completion_id,
                entry_id=entry_id,
                user_id=user_id,
                state=MealCompletionState.REOPENED,
                version=3,
            ),
        ),
    ]
    preserved_payload = _legacy_completion_payload(
        completion_id=completion_id,
        entry_id=entry_id,
        user_id=user_id,
        state=MealCompletionState.RECORDED,
        version=1,
    )
    preserved_payload["outcome"] = "skipped"
    preserved_payload["outcome_note"] = "ate out"
    with Session(integration_engine) as session:
        original_receipts = list(
            session.execute(select(CompletionOperation.id, CompletionOperation.result_payload))
        )
        original_completions = list(
            session.execute(
                select(MealCompletion.id, MealCompletion.outcome, MealCompletion.outcome_note)
            )
        )

    try:
        command.downgrade(config, "f2b8d4e6a917")
        with Session(integration_engine) as session:
            session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
            session.add(Household(id=household_id, name="Legacy receipts", locale="es"))
            session.flush()
            member = HouseholdMember(
                household_id=household_id,
                user_id=user_id,
                role=MembershipRole.OWNER,
                status=MembershipStatus.ACTIVE,
            )
            session.add(member)
            session.flush()
            session.add_all(
                [
                    CompletionOperation(
                        household_id=household_id,
                        operation=operation,
                        idempotency_key=key,
                        request_hash=fingerprint,
                        result_payload=payload,
                    )
                    for operation, key, fingerprint, payload in operations
                ]
            )
            session.add(
                CompletionOperation(
                    household_id=household_id,
                    operation="meal_entry_skip",
                    idempotency_key="legacy-existing-outcome",
                    result_payload=preserved_payload,
                )
            )
            session.add(
                CompletionOperation(
                    household_id=household_id,
                    operation="meal_entry_complete",
                    idempotency_key="legacy-null-payload",
                    result_payload=None,
                )
            )
            session.commit()

        command.upgrade(config, "d3c72b91a84f")
        with Session(integration_engine) as session:
            member = session.scalar(
                select(HouseholdMember).where(
                    HouseholdMember.household_id == household_id,
                    HouseholdMember.user_id == user_id,
                )
            )
            assert member is not None
            for operation, key, _fingerprint, _payload in operations:
                stored = session.scalar(
                    select(CompletionOperation.result_payload).where(
                        CompletionOperation.household_id == household_id,
                        CompletionOperation.operation == operation,
                        CompletionOperation.idempotency_key == key,
                    )
                )
                assert stored is not None
                assert stored["outcome"] == "cooked"
                assert stored["outcome_note"] is None

            preserved = session.scalar(
                select(CompletionOperation.result_payload).where(
                    CompletionOperation.household_id == household_id,
                    CompletionOperation.idempotency_key == "legacy-existing-outcome",
                )
            )
            assert preserved is not None
            assert preserved["outcome"] == "skipped"
            assert preserved["outcome_note"] == "ate out"

            replayed_complete = complete_entry(
                session,
                member,
                plan_id,
                entry_id,
                MealCompletionCreate(),
                receipt_keys["meal_entry_complete"],
            )
            replayed_correct = correct_line(
                session,
                member,
                completion_id,
                line_id,
                expected_version=1,
                actual_amount=Decimal("0.5"),
                unit="g",
                idempotency_key=receipt_keys["meal_completion_line_correct"],
            )
            replayed_reopen = reopen_completion(
                session,
                member,
                completion_id,
                expected_version=2,
                reason="legacy reopen",
                idempotency_key=receipt_keys["meal_completion_reopen"],
            )
            for replay in (replayed_complete, replayed_correct, replayed_reopen):
                assert MealCompletionResponse.model_validate(replay.payload).outcome == "cooked"
                assert replay.payload["outcome_note"] is None

            null_payload = session.scalar(
                select(CompletionOperation.result_payload).where(
                    CompletionOperation.household_id == household_id,
                    CompletionOperation.idempotency_key == "legacy-null-payload",
                )
            )
            assert null_payload is None

        command.downgrade(config, "f2b8d4e6a917")
        with Session(integration_engine) as session:
            for key in (
                *[operation[1] for operation in operations],
                "legacy-existing-outcome",
            ):
                stored = session.scalar(
                    select(CompletionOperation.result_payload).where(
                        CompletionOperation.household_id == household_id,
                        CompletionOperation.idempotency_key == key,
                    )
                )
                assert stored is not None
                assert "outcome" not in stored
                assert "outcome_note" not in stored
            null_payload = session.scalar(
                select(CompletionOperation.result_payload).where(
                    CompletionOperation.household_id == household_id,
                    CompletionOperation.idempotency_key == "legacy-null-payload",
                )
            )
            assert null_payload is None
    finally:
        command.upgrade(config, "head")
        with Session(integration_engine) as session:
            for receipt_id, result_payload in original_receipts:
                session.execute(
                    update(CompletionOperation)
                    .where(CompletionOperation.id == receipt_id)
                    .values(result_payload=result_payload)
                )
            for completion_id, outcome, outcome_note in original_completions:
                session.execute(
                    update(MealCompletion)
                    .where(MealCompletion.id == completion_id)
                    .values(outcome=outcome, outcome_note=outcome_note)
                )
            member = session.scalar(
                select(HouseholdMember).where(
                    HouseholdMember.household_id == household_id,
                    HouseholdMember.user_id == user_id,
                )
            )
            household = session.get(Household, household_id)
            user = session.get(AppUser, user_id)
            if member is not None:
                session.delete(member)
            if household is not None:
                session.delete(household)
            if user is not None:
                session.delete(user)
            session.commit()
