import json
from threading import Event, Thread
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from uribap_api.api.memory_schemas import DinerCreate, DinerUpdate, MemoryCreate, MemoryUpdate
from uribap_api.application import memory_service
from uribap_api.domain.household.memory import MemoryKind
from uribap_api.domain.identity.policies import MembershipRole, MembershipStatus
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.persistence.event_models import DomainEvent
from uribap_api.infrastructure.persistence.household_models import (
    Household,
    HouseholdDiner,
    HouseholdMember,
    HouseholdMemory,
)
from uribap_api.infrastructure.persistence.identity_models import AppUser

pytestmark = pytest.mark.integration


def _member(
    session: Session,
    name: str,
    *,
    role: MembershipRole = MembershipRole.MEMBER,
    status: MembershipStatus = MembershipStatus.ACTIVE,
) -> tuple[Household, HouseholdMember]:
    user_id, household_id = uuid4(), uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    session.add(Household(id=household_id, name=name, locale="es", timezone="UTC"))
    member = HouseholdMember(
        household_id=household_id,
        user_id=user_id,
        role=role,
        status=status,
    )
    session.add(member)
    session.flush()
    household = session.get(Household, household_id)
    assert household is not None
    return household, member


def _additional_member(
    session: Session,
    household: Household,
    *,
    role: MembershipRole = MembershipRole.MEMBER,
    status: MembershipStatus = MembershipStatus.ACTIVE,
) -> HouseholdMember:
    user_id = uuid4()
    session.add(AppUser(id=user_id, email=f"{user_id}@example.test", email_verified=True))
    member = HouseholdMember(
        household_id=household.id,
        user_id=user_id,
        role=role,
        status=status,
    )
    session.add(member)
    session.flush()
    return member


@pytest.mark.parametrize(
    "role",
    [MembershipRole.OWNER, MembershipRole.ADMIN, MembershipRole.MEMBER],
)
def test_all_active_household_roles_can_write_memory_profiles(integration_engine, role) -> None:
    with Session(integration_engine) as session:
        _household, member = _member(session, f"Role {role.value}", role=role)

        created = memory_service.create_diner(
            session,
            member,
            DinerCreate(display_name=f"Diner {role.value}"),
            f"role-diner-{role.value}-{uuid4()}",
        )

        assert created.payload["display_name"] == f"Diner {role.value}"


def test_diner_create_update_archive_and_active_name_reuse(integration_engine) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session, "Diner lifecycle")
        linked_member = _additional_member(session, household)
        first = memory_service.create_diner(
            session,
            member,
            DinerCreate(display_name="  Alex  ", member_user_id=linked_member.user_id),
            "diner-create-alex",
        )
        first_id = UUID(first.payload["id"])
        assert first.payload["display_name"] == "Alex"
        assert first.payload["member_user_id"] == str(linked_member.user_id)
        assert first.payload["version"] == 1

        second = memory_service.create_diner(
            session, member, DinerCreate(display_name="Guest"), "diner-create-guest"
        )
        second_id = UUID(second.payload["id"])
        assert [diner.id for diner in memory_service.list_diners(session, member)] == [
            first_id,
            second_id,
        ]

        with pytest.raises(DomainError) as duplicate_name:
            memory_service.create_diner(
                session, member, DinerCreate(display_name="aLeX"), "duplicate-casefold-name"
            )
        assert duplicate_name.value.status_code == 409

        with pytest.raises(DomainError) as duplicate_link:
            memory_service.create_diner(
                session,
                member,
                DinerCreate(display_name="Second profile", member_user_id=linked_member.user_id),
                "duplicate-member-link",
            )
        assert duplicate_link.value.status_code == 409
        assert duplicate_link.value.code == "invalid_member_link"

        with pytest.raises(DomainError) as renamed_duplicate:
            memory_service.update_diner(
                session,
                member,
                second_id,
                DinerUpdate(expected_version=1, display_name="ALEX"),
            )
        assert renamed_duplicate.value.status_code == 409

        updated = memory_service.update_diner(
            session,
            member,
            first_id,
            DinerUpdate(expected_version=1, display_name="Alex II", member_user_id=None),
        )
        assert updated.display_name == "Alex II"
        assert updated.member_user_id is None
        assert updated.version == 2

        with pytest.raises(DomainError) as stale:
            memory_service.update_diner(
                session,
                member,
                first_id,
                DinerUpdate(expected_version=1, display_name="Stale rename"),
            )
        assert stale.value.status_code == 409

        memory_service.archive_diner(session, member, first_id)
        archived = session.get(HouseholdDiner, first_id)
        assert archived is not None
        assert archived.archived_at is not None
        assert archived.version == 3
        event_count = session.scalar(
            select(func.count())
            .select_from(DomainEvent)
            .where(
                DomainEvent.household_id == household.id,
                DomainEvent.kind == "diner.archived",
                DomainEvent.aggregate_id == first_id,
            )
        )
        memory_service.archive_diner(session, member, first_id)
        assert (
            session.scalar(
                select(func.count())
                .select_from(DomainEvent)
                .where(
                    DomainEvent.household_id == household.id,
                    DomainEvent.kind == "diner.archived",
                    DomainEvent.aggregate_id == first_id,
                )
            )
            == event_count
            == 1
        )

        reused_name = memory_service.create_diner(
            session, member, DinerCreate(display_name="ALEX II"), "reused-archived-name"
        )
        assert reused_name.payload["display_name"] == "ALEX II"
        assert UUID(reused_name.payload["id"]) != first_id
        diner_events = list(
            session.scalars(
                select(DomainEvent).where(
                    DomainEvent.household_id == household.id,
                    DomainEvent.kind.like("diner.%"),
                )
            )
        )
        assert {"diner.created", "diner.updated", "diner.archived"}.issubset(
            {event.kind for event in diner_events}
        )
        assert all("Alex II" not in json.dumps(event.payload) for event in diner_events)


def test_diner_links_require_active_same_household_members_and_ids_are_scoped(
    integration_engine,
) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session, "Diner tenant")
        linked_member = _additional_member(session, household)
        revoked_member = _additional_member(session, household, status=MembershipStatus.REVOKED)
        foreign_household, foreign_member = _member(session, "Foreign diner tenant")

        linked = memory_service.create_diner(
            session,
            member,
            DinerCreate(display_name="Linked", member_user_id=linked_member.user_id),
            "link-active-member",
        )
        for invalid_member in (revoked_member, foreign_member):
            with pytest.raises(DomainError) as invalid_link:
                memory_service.create_diner(
                    session,
                    member,
                    DinerCreate(
                        display_name=f"Invalid {invalid_member.user_id}",
                        member_user_id=invalid_member.user_id,
                    ),
                    f"invalid-member-{invalid_member.user_id}",
                )
            assert invalid_link.value.status_code == 422
            assert invalid_link.value.code == "invalid_member_link"

        foreign_diner = memory_service.create_diner(
            session,
            foreign_member,
            DinerCreate(display_name="Foreign diner"),
            "foreign-diner",
        )
        foreign_id = UUID(foreign_diner.payload["id"])
        with pytest.raises(DomainError) as update_foreign:
            memory_service.update_diner(
                session,
                member,
                foreign_id,
                DinerUpdate(expected_version=1, display_name="Not accessible"),
            )
        assert update_foreign.value.status_code == 404
        with pytest.raises(DomainError) as archive_foreign:
            memory_service.archive_diner(session, member, foreign_id)
        assert archive_foreign.value.status_code == 404

        with pytest.raises(DomainError) as unknown:
            memory_service.update_diner(
                session,
                member,
                uuid4(),
                DinerUpdate(expected_version=1, display_name="Unknown"),
            )
        assert unknown.value.status_code == 404
        assert linked.payload["member_user_id"] == str(linked_member.user_id)
        assert foreign_household.id != household.id


def test_member_link_unique_constraint_races_return_invalid_member_link(
    integration_engine, monkeypatch
) -> None:
    with Session(integration_engine) as session:
        _household, member = _member(session, "Diner member-link race")
        linked = memory_service.create_diner(
            session,
            member,
            DinerCreate(display_name="Already linked", member_user_id=member.user_id),
            "member-link-race-existing",
        )
        unlinked = memory_service.create_diner(
            session, member, DinerCreate(display_name="To link"), "member-link-race-unlinked"
        )
        monkeypatch.setattr(
            memory_service,
            "_validate_member_link",
            lambda *_args, **_kwargs: None,
        )

        with pytest.raises(DomainError) as create_conflict:
            memory_service.create_diner(
                session,
                member,
                DinerCreate(display_name="Create race", member_user_id=member.user_id),
                None,
            )
        assert create_conflict.value.code == "invalid_member_link"
        assert create_conflict.value.status_code == 409

        with pytest.raises(DomainError) as update_conflict:
            memory_service.update_diner(
                session,
                member,
                UUID(unlinked.payload["id"]),
                DinerUpdate(expected_version=1, member_user_id=member.user_id),
            )
        assert update_conflict.value.code == "invalid_member_link"
        assert update_conflict.value.status_code == 409
        assert linked.payload["member_user_id"] == str(member.user_id)


def test_diner_create_idempotency_replay_records_one_private_event(
    integration_engine, caplog
) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session, "Diner receipt")
        display_name = f"Private diner {uuid4()}"
        key = f"diner-replay-{uuid4()}"

        first = memory_service.create_diner(
            session, member, DinerCreate(display_name=display_name), key
        )
        replay = memory_service.create_diner(
            session, member, DinerCreate(display_name=display_name), key
        )

        assert replay.payload == first.payload
        assert (
            session.scalar(
                select(func.count())
                .select_from(HouseholdDiner)
                .where(HouseholdDiner.household_id == household.id)
            )
            == 1
        )
        event = session.scalar(
            select(DomainEvent).where(
                DomainEvent.household_id == household.id,
                DomainEvent.kind == "diner.created",
            )
        )
        assert event is not None
        assert event.payload["diner_id"] == str(first.payload["id"])
        assert display_name not in json.dumps(event.payload)
        assert display_name not in caplog.text


def test_memory_crud_scopes_profile_idempotency_and_event_privacy(
    integration_engine, caplog
) -> None:
    with Session(integration_engine) as session:
        household, member = _member(session, "Memory lifecycle")
        foreign_household, foreign_member = _member(session, "Foreign memory")
        diner = memory_service.create_diner(
            session, member, DinerCreate(display_name="Memory diner"), "memory-diner"
        )
        diner_id = UUID(diner.payload["id"])
        foreign_diner = memory_service.create_diner(
            session,
            foreign_member,
            DinerCreate(display_name="Foreign diner"),
            "foreign-memory-diner",
        )
        foreign_diner_id = UUID(foreign_diner.payload["id"])
        secret_content = f"Secret preference {uuid4()}"
        key = f"memory-replay-{uuid4()}"

        created = memory_service.create_memory(
            session,
            member,
            MemoryCreate(
                kind=MemoryKind.RESTRICTION,
                content=f"  {secret_content}  ",
                diner_id=diner_id,
            ),
            key,
        )
        replay = memory_service.create_memory(
            session,
            member,
            MemoryCreate(
                kind=MemoryKind.RESTRICTION,
                content=secret_content,
                diner_id=diner_id,
            ),
            key,
        )
        memory_id = UUID(created.payload["id"])
        assert replay.payload == created.payload
        assert created.payload["content"] == secret_content
        assert created.payload["kind"] == "restriction"
        assert (
            session.scalar(
                select(func.count())
                .select_from(HouseholdMemory)
                .where(HouseholdMemory.household_id == household.id)
            )
            == 1
        )

        household_memory = memory_service.create_memory(
            session,
            member,
            MemoryCreate(kind=MemoryKind.NOTE, content="Household note"),
            f"household-memory-{uuid4()}",
        )
        household_memory_id = UUID(household_memory.payload["id"])
        household_like = memory_service.create_memory(
            session,
            member,
            MemoryCreate(kind=MemoryKind.LIKE, content="Household likes soup"),
            f"household-like-{uuid4()}",
        )
        household_like_id = UUID(household_like.payload["id"])
        diner_like = memory_service.create_memory(
            session,
            member,
            MemoryCreate(kind=MemoryKind.LIKE, content="Likes lentils", diner_id=diner_id),
            f"diner-like-{uuid4()}",
        )

        all_memories = memory_service.list_memories(session, member, scope="all")
        assert len(all_memories) == 4
        assert all_memories[0].diner_id is None
        assert all_memories[0].kind == MemoryKind.LIKE
        assert all(row.household_id == household.id for row in all_memories)
        household_scope = memory_service.list_memories(session, member, scope="household")
        assert [row.kind for row in household_scope] == [MemoryKind.LIKE, MemoryKind.NOTE]
        assert {row.id for row in household_scope} == {
            household_memory_id,
            household_like_id,
        }
        diner_scope = memory_service.list_memories(session, member, scope="diner")
        assert [row.kind for row in diner_scope] == [MemoryKind.LIKE, MemoryKind.RESTRICTION]
        assert {row.id for row in diner_scope} == {
            memory_id,
            UUID(diner_like.payload["id"]),
        }
        filtered = memory_service.list_memories(
            session, member, diner_id=diner_id, scope="all", limit=1
        )
        assert len(filtered) == 1
        assert filtered[0].diner_id == diner_id

        moved = memory_service.update_memory(
            session,
            member,
            memory_id,
            MemoryUpdate(expected_version=1, content="Updated restriction", diner_id=None),
        )
        assert moved.diner_id is None
        assert moved.content == "Updated restriction"
        assert moved.version == 2
        with pytest.raises(DomainError) as stale:
            memory_service.update_memory(
                session,
                member,
                memory_id,
                MemoryUpdate(expected_version=1, content="Stale update"),
            )
        assert stale.value.status_code == 409

        with pytest.raises(DomainError) as foreign_target:
            memory_service.create_memory(
                session,
                member,
                MemoryCreate(
                    kind=MemoryKind.NOTE,
                    content="Foreign diner target",
                    diner_id=foreign_diner_id,
                ),
                f"foreign-target-{uuid4()}",
            )
        assert foreign_target.value.status_code == 404
        with pytest.raises(DomainError) as foreign_diner_filter:
            memory_service.list_memories(session, member, diner_id=foreign_diner_id, scope="all")
        assert foreign_diner_filter.value.status_code == 404

        archived_target = memory_service.create_diner(
            session, member, DinerCreate(display_name="Archived target"), "archived-target"
        )
        archived_target_id = UUID(archived_target.payload["id"])
        memory_service.archive_diner(session, member, archived_target_id)
        with pytest.raises(DomainError) as archived_target_error:
            memory_service.create_memory(
                session,
                member,
                MemoryCreate(
                    kind=MemoryKind.NOTE,
                    content="Archived diner target",
                    diner_id=archived_target_id,
                ),
                f"archived-target-memory-{uuid4()}",
            )
        assert archived_target_error.value.status_code == 404

        foreign_memory_result = memory_service.create_memory(
            session,
            foreign_member,
            MemoryCreate(kind=MemoryKind.NOTE, content="Foreign memory"),
            f"foreign-memory-{uuid4()}",
        )
        with pytest.raises(DomainError) as foreign_memory:
            memory_service.update_memory(
                session,
                member,
                UUID(foreign_memory_result.payload["id"]),
                MemoryUpdate(expected_version=1, content="Not accessible"),
            )
        assert foreign_memory.value.status_code == 404
        assert UUID(foreign_memory_result.payload["id"]) not in {
            row.id for row in memory_service.list_memories(session, member)
        }
        with pytest.raises(DomainError) as unknown_memory:
            memory_service.archive_memory(session, member, uuid4())
        assert unknown_memory.value.status_code == 404

        memory_service.archive_memory(session, member, household_memory_id)
        archived_event_count = session.scalar(
            select(func.count())
            .select_from(DomainEvent)
            .where(
                DomainEvent.household_id == household.id,
                DomainEvent.kind == "memory.archived",
                DomainEvent.aggregate_id == household_memory_id,
            )
        )
        memory_service.archive_memory(session, member, household_memory_id)
        assert (
            session.scalar(
                select(func.count())
                .select_from(DomainEvent)
                .where(
                    DomainEvent.household_id == household.id,
                    DomainEvent.kind == "memory.archived",
                    DomainEvent.aggregate_id == household_memory_id,
                )
            )
            == archived_event_count
            == 1
        )
        active_memories = memory_service.list_memories(session, member)
        assert household_memory_id not in {row.id for row in active_memories}
        archived_memories = memory_service.list_memories(session, member, include_archived=True)
        assert household_memory_id in {row.id for row in archived_memories}

        profile = memory_service.get_memory_profile(session, member)
        assert {row.id for row in profile.household} == {memory_id, household_like_id}
        assert len(profile.diners) == 1
        assert profile.diners[0].diner.id == diner_id
        assert {row.id for row in profile.diners[0].memories} == {UUID(diner_like.payload["id"])}

        memory_service.archive_diner(session, member, diner_id)
        archived_profile = memory_service.get_memory_profile(session, member)
        assert archived_profile.diners == []
        assert all(row.diner_id is None for row in archived_profile.household)
        assert {row.id for row in memory_service.list_memories(session, member)} == {
            memory_id,
            household_like_id,
        }
        assert {
            row.id for row in memory_service.list_memories(session, member, include_archived=True)
        } == {
            memory_id,
            UUID(diner_like.payload["id"]),
            household_memory_id,
            household_like_id,
        }
        with pytest.raises(DomainError) as archive_foreign:
            memory_service.archive_memory(
                session,
                member,
                UUID(
                    memory_service.create_memory(
                        session,
                        foreign_member,
                        MemoryCreate(kind=MemoryKind.NOTE, content="Foreign archived memory"),
                        f"foreign-archive-{uuid4()}",
                    ).payload["id"]
                ),
            )
        assert archive_foreign.value.status_code == 404

        events = list(
            session.scalars(select(DomainEvent).where(DomainEvent.household_id == household.id))
        )
        event_kinds = {event.kind for event in events}
        assert {
            "memory.created",
            "memory.updated",
            "memory.archived",
            "diner.archived",
        }.issubset(event_kinds)
        assert all(secret_content not in json.dumps(event.payload) for event in events)
        assert all("Memory diner" not in json.dumps(event.payload) for event in events)
        assert secret_content not in caplog.text
        assert "Memory diner" not in caplog.text
        memory_events = [event for event in events if event.kind.startswith("memory.")]
        assert all(
            set(event.payload).issubset({"memory_id", "diner_id", "kind"})
            and "kind" in event.payload
            and event.payload.get("memory_id") not in (None, "None")
            for event in memory_events
        )
        diner_events = [event for event in events if event.kind.startswith("diner.")]
        assert all(
            set(event.payload).issubset({"diner_id", "member_user_id"})
            and "diner_id" in event.payload
            and event.payload.get("diner_id") not in (None, "None")
            for event in diner_events
        )
        assert foreign_household.id != household.id


def test_memory_profile_loads_active_memories_in_one_query(integration_engine) -> None:
    with Session(integration_engine) as session:
        _household, member = _member(session, "Memory profile query")
        first_diner = memory_service.create_diner(
            session, member, DinerCreate(display_name="Zoe"), "profile-diner-zoe"
        )
        second_diner = memory_service.create_diner(
            session, member, DinerCreate(display_name="Ana"), "profile-diner-ana"
        )
        first_diner_id = UUID(first_diner.payload["id"])
        second_diner_id = UUID(second_diner.payload["id"])
        memory_service.create_memory(
            session,
            member,
            MemoryCreate(kind=MemoryKind.NOTE, content="House note"),
            "profile-house-note",
        )
        memory_service.create_memory(
            session,
            member,
            MemoryCreate(kind=MemoryKind.LIKE, content="House like"),
            "profile-house-like",
        )
        memory_service.create_memory(
            session,
            member,
            MemoryCreate(
                kind=MemoryKind.RESTRICTION,
                content="Zoe restriction",
                diner_id=first_diner_id,
            ),
            "profile-zoe-restriction",
        )
        memory_service.create_memory(
            session,
            member,
            MemoryCreate(
                kind=MemoryKind.LIKE,
                content="Ana like",
                diner_id=second_diner_id,
            ),
            "profile-ana-like",
        )
        membership = HouseholdMember(
            household_id=member.household_id,
            user_id=member.user_id,
            role=member.role,
            status=member.status,
        )

    memory_queries: list[str] = []

    def count_memory_query(_connection, _cursor, statement, _parameters, _context, _many) -> None:
        normalized_statement = statement.casefold()
        if (
            normalized_statement.lstrip().startswith("select")
            and "household_memory" in normalized_statement
        ):
            memory_queries.append(statement)

    event.listen(integration_engine, "before_cursor_execute", count_memory_query)
    try:
        with Session(integration_engine) as session:
            profile = memory_service.get_memory_profile(session, membership)
    finally:
        event.remove(integration_engine, "before_cursor_execute", count_memory_query)

    assert len(memory_queries) == 1
    assert [memory.kind for memory in profile.household] == [MemoryKind.LIKE, MemoryKind.NOTE]
    assert [diner.diner.display_name for diner in profile.diners] == ["Ana", "Zoe"]
    assert [memory.kind for memory in profile.diners[0].memories] == [MemoryKind.LIKE]
    assert [memory.kind for memory in profile.diners[1].memories] == [MemoryKind.RESTRICTION]


def test_memory_diner_validation_and_archive_wait_for_row_lock(integration_engine) -> None:
    with Session(integration_engine) as session:
        _household, member = _member(session, "Memory diner lock")
        diner = memory_service.create_diner(
            session, member, DinerCreate(display_name="Locked diner"), "locked-diner"
        )
        diner_id = UUID(diner.payload["id"])
        household_memory = memory_service.create_memory(
            session,
            member,
            MemoryCreate(kind=MemoryKind.NOTE, content="Move to diner"),
            "move-memory-to-diner",
        )
        memory_id = UUID(household_memory.payload["id"])
        membership = HouseholdMember(
            household_id=member.household_id,
            user_id=member.user_id,
            role=member.role,
            status=member.status,
        )

    def blocks_on_diner_lock(operation) -> bool:
        lock_queries: list[str] = []

        def capture_diner_lock(
            _connection, _cursor, statement, _parameters, _context, _many
        ) -> None:
            normalized_statement = statement.casefold()
            if "household_diner" in normalized_statement and "for update" in normalized_statement:
                lock_queries.append(statement)

        with integration_engine.connect() as lock_connection:
            lock_connection.execute(
                select(HouseholdDiner.id).where(HouseholdDiner.id == diner_id).with_for_update()
            )
            started = Event()
            finished = Event()
            failures: list[BaseException] = []

            def run_operation() -> None:
                started.set()
                try:
                    with Session(integration_engine) as worker_session:
                        operation(worker_session)
                except BaseException as exc:
                    failures.append(exc)
                finally:
                    finished.set()

            worker = Thread(target=run_operation, daemon=True)
            event.listen(integration_engine, "before_cursor_execute", capture_diner_lock)
            try:
                worker.start()
                worker_started = started.wait(timeout=5)
                was_blocked = worker_started and not finished.wait(timeout=0.5)
                lock_connection.commit()
                worker.join(timeout=10)
            finally:
                event.remove(integration_engine, "before_cursor_execute", capture_diner_lock)

        assert worker_started
        assert not worker.is_alive()
        assert not failures
        assert lock_queries
        return was_blocked

    assert blocks_on_diner_lock(
        lambda session: memory_service.create_memory(
            session,
            membership,
            MemoryCreate(
                kind=MemoryKind.NOTE,
                content="Created while diner is active",
                diner_id=diner_id,
            ),
            f"locked-create-{uuid4()}",
        )
    )
    assert blocks_on_diner_lock(
        lambda session: memory_service.update_memory(
            session,
            membership,
            memory_id,
            MemoryUpdate(expected_version=1, diner_id=diner_id),
        )
    )
    assert blocks_on_diner_lock(
        lambda session: memory_service.archive_diner(session, membership, diner_id)
    )
