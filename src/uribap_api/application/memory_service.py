from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

import psycopg
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.api.memory_schemas import (
    DinerCreate,
    DinerMemoryProfile,
    DinerResponse,
    DinerUpdate,
    HouseholdMemoryProfile,
    MemoryCreate,
    MemoryResponse,
    MemoryUpdate,
)
from uribap_api.application.event_service import record_event
from uribap_api.domain.events.policies import DomainEventKind
from uribap_api.domain.identity.policies import MembershipStatus
from uribap_api.domain.shared.errors import DomainError
from uribap_api.domain.shared.fingerprint import operation_fingerprint
from uribap_api.infrastructure.persistence.household_models import (
    HouseholdDiner,
    HouseholdMember,
    HouseholdMemory,
)
from uribap_api.infrastructure.persistence.planning_models import MealPlanOperation


@dataclass(frozen=True)
class MemoryMutationResult:
    payload: dict[str, Any]


def _not_found(resource: str) -> DomainError:
    return DomainError(
        "not_found", f"{resource} not found", f"The {resource.lower()} could not be found.", 404
    )


def _conflict(title: str, detail: str) -> DomainError:
    return DomainError("conflict", title, detail, 409)


def _is_member_link_unique_violation(exc: IntegrityError) -> bool:
    return (
        isinstance(exc.orig, psycopg.errors.UniqueViolation)
        and exc.orig.diag.constraint_name == "uq_household_diner_member"
    )


def _diner_member_link_conflict() -> DomainError:
    return DomainError(
        "invalid_member_link",
        "Diner member conflict",
        "A diner is already linked to this household member.",
        409,
    )


def _find_receipt(
    session: Session,
    membership: HouseholdMember,
    operation: str,
    key: str,
) -> MealPlanOperation | None:
    return session.scalar(
        select(MealPlanOperation).where(
            MealPlanOperation.household_id == membership.household_id,
            MealPlanOperation.operation == operation,
            MealPlanOperation.idempotency_key == key,
        )
    )


def _check_receipt(receipt: MealPlanOperation | None, fingerprint: str) -> dict[str, Any] | None:
    if receipt is None:
        return None
    if receipt.request_hash != fingerprint:
        raise _conflict(
            "Idempotency key conflict",
            "The key was already used for a different household memory operation.",
        )
    return receipt.result_payload


def _store_receipt(
    session: Session,
    membership: HouseholdMember,
    operation: str,
    key: str | None,
    fingerprint: str,
    payload: dict[str, Any],
) -> None:
    if key is None:
        return
    session.add(
        MealPlanOperation(
            household_id=membership.household_id,
            operation=operation,
            idempotency_key=key,
            request_hash=fingerprint,
            result_payload=payload,
        )
    )


def _replay_or_conflict(
    session: Session,
    membership: HouseholdMember,
    operation: str,
    key: str | None,
    fingerprint: str,
    detail: str,
    exc: IntegrityError,
) -> dict[str, Any]:
    session.rollback()
    if key is not None:
        replay = _check_receipt(_find_receipt(session, membership, operation, key), fingerprint)
        if replay is not None:
            return replay
    raise _conflict("Household memory conflict", detail) from exc


def _get_diner(
    session: Session,
    membership: HouseholdMember,
    diner_id: UUID,
    *,
    include_archived: bool = False,
    lock: bool = False,
) -> HouseholdDiner:
    statement = select(HouseholdDiner).where(
        HouseholdDiner.id == diner_id,
        HouseholdDiner.household_id == membership.household_id,
    )
    if not include_archived:
        statement = statement.where(HouseholdDiner.archived_at.is_(None))
    if lock:
        statement = statement.with_for_update()
    diner = session.scalar(statement)
    if diner is None:
        raise _not_found("Diner")
    return diner


def get_diner(session: Session, membership: HouseholdMember, diner_id: UUID) -> HouseholdDiner:
    return _get_diner(session, membership, diner_id)


def find_active_diner_by_name(
    session: Session, membership: HouseholdMember, display_name: str
) -> HouseholdDiner | None:
    return session.scalar(
        select(HouseholdDiner).where(
            HouseholdDiner.household_id == membership.household_id,
            HouseholdDiner.archived_at.is_(None),
            func.lower(HouseholdDiner.display_name) == display_name.strip().lower(),
        )
    )


def _get_memory(
    session: Session,
    membership: HouseholdMember,
    memory_id: UUID,
    *,
    include_archived: bool = False,
    lock: bool = False,
) -> HouseholdMemory:
    statement = select(HouseholdMemory).where(
        HouseholdMemory.id == memory_id,
        HouseholdMemory.household_id == membership.household_id,
    )
    if not include_archived:
        statement = statement.where(HouseholdMemory.archived_at.is_(None))
    if lock:
        statement = statement.with_for_update()
    memory = session.scalar(statement)
    if memory is None:
        raise _not_found("Memory")
    return memory


def get_memory(session: Session, membership: HouseholdMember, memory_id: UUID) -> HouseholdMemory:
    return _get_memory(session, membership, memory_id)


def _validate_member_link(
    session: Session,
    membership: HouseholdMember,
    member_user_id: UUID | None,
    *,
    exclude_diner_id: UUID | None = None,
) -> None:
    if member_user_id is None:
        return
    active_member_id = session.scalar(
        select(HouseholdMember.id).where(
            HouseholdMember.household_id == membership.household_id,
            HouseholdMember.user_id == member_user_id,
            HouseholdMember.status == MembershipStatus.ACTIVE,
        )
    )
    if active_member_id is None:
        raise DomainError(
            "invalid_member_link",
            "Invalid diner member",
            "The linked user must be an active member of this household.",
            422,
        )
    statement = select(HouseholdDiner.id).where(
        HouseholdDiner.household_id == membership.household_id,
        HouseholdDiner.member_user_id == member_user_id,
    )
    if exclude_diner_id is not None:
        statement = statement.where(HouseholdDiner.id != exclude_diner_id)
    existing_diner_id = session.scalar(statement)
    if existing_diner_id is not None:
        raise DomainError(
            "invalid_member_link",
            "Diner member conflict",
            "A diner is already linked to this household member.",
            409,
        )


def _assert_unique_name(
    session: Session,
    membership: HouseholdMember,
    display_name: str,
    *,
    exclude_diner_id: UUID | None = None,
) -> None:
    statement = select(HouseholdDiner.id).where(
        HouseholdDiner.household_id == membership.household_id,
        HouseholdDiner.archived_at.is_(None),
        func.lower(HouseholdDiner.display_name) == display_name.lower(),
    )
    if exclude_diner_id is not None:
        statement = statement.where(HouseholdDiner.id != exclude_diner_id)
    if session.scalar(statement) is not None:
        raise _conflict(
            "Diner name conflict",
            "An active diner with this name already exists in the household.",
        )


def _validate_memory_diner(
    session: Session,
    membership: HouseholdMember,
    diner_id: UUID | None,
) -> None:
    if diner_id is None:
        return
    _get_diner(session, membership, diner_id, lock=True)


def list_diners(
    session: Session,
    membership: HouseholdMember,
    *,
    include_archived: bool = False,
) -> list[HouseholdDiner]:
    statement = select(HouseholdDiner).where(HouseholdDiner.household_id == membership.household_id)
    if not include_archived:
        statement = statement.where(HouseholdDiner.archived_at.is_(None))
    return list(
        session.scalars(
            statement.order_by(func.lower(HouseholdDiner.display_name), HouseholdDiner.id)
        )
    )


def list_memories(
    session: Session,
    membership: HouseholdMember,
    *,
    diner_id: UUID | None = None,
    scope: Literal["all", "household", "diner"] = "all",
    include_archived: bool = False,
    limit: int | None = 200,
) -> list[HouseholdMemory]:
    if diner_id is not None:
        diner_exists = session.scalar(
            select(HouseholdDiner.id).where(
                HouseholdDiner.id == diner_id,
                HouseholdDiner.household_id == membership.household_id,
            )
        )
        if diner_exists is None:
            raise _not_found("Diner")

    statement = (
        select(HouseholdMemory)
        .outerjoin(
            HouseholdDiner,
            and_(
                HouseholdDiner.id == HouseholdMemory.diner_id,
                HouseholdDiner.household_id == HouseholdMemory.household_id,
            ),
        )
        .where(HouseholdMemory.household_id == membership.household_id)
        .where(
            or_(
                HouseholdMemory.diner_id.is_(None),
                HouseholdDiner.id.is_not(None),
            )
        )
    )
    if not include_archived:
        statement = statement.where(
            HouseholdMemory.archived_at.is_(None),
            or_(
                HouseholdMemory.diner_id.is_(None),
                and_(
                    HouseholdDiner.id.is_not(None),
                    HouseholdDiner.archived_at.is_(None),
                ),
            ),
        )
    if scope == "household":
        statement = statement.where(HouseholdMemory.diner_id.is_(None))
    elif scope == "diner":
        statement = statement.where(HouseholdMemory.diner_id.is_not(None))
    elif scope != "all":
        raise DomainError(
            "validation_error", "Invalid memory scope", "The scope is not supported.", 422
        )
    if diner_id is not None:
        statement = statement.where(HouseholdMemory.diner_id == diner_id)
    statement = statement.order_by(
        case((HouseholdMemory.diner_id.is_(None), 0), else_=1),
        HouseholdMemory.diner_id,
        HouseholdMemory.kind,
        HouseholdMemory.created_at,
        HouseholdMemory.id,
    )
    if limit is not None:
        statement = statement.limit(limit)
    return list(session.scalars(statement))


def get_memory_profile(session: Session, membership: HouseholdMember) -> HouseholdMemoryProfile:
    memories = list_memories(session, membership, scope="all", limit=None)
    household_memories = [
        MemoryResponse.model_validate(memory) for memory in memories if memory.diner_id is None
    ]
    diner_memories: dict[UUID, list[HouseholdMemory]] = {}
    for memory in memories:
        if memory.diner_id is not None:
            diner_memories.setdefault(memory.diner_id, []).append(memory)
    diner_profiles = [
        DinerMemoryProfile(
            diner=DinerResponse.model_validate(diner),
            memories=[
                MemoryResponse.model_validate(memory) for memory in diner_memories.get(diner.id, [])
            ],
        )
        for diner in list_diners(session, membership)
    ]
    return HouseholdMemoryProfile(household=household_memories, diners=diner_profiles)


def create_diner(
    session: Session,
    membership: HouseholdMember,
    payload: DinerCreate,
    idempotency_key: str | None,
) -> MemoryMutationResult:
    operation = "household_diner_create"
    fingerprint = operation_fingerprint(
        operation,
        {
            "display_name": payload.display_name,
            "member_user_id": str(payload.member_user_id) if payload.member_user_id else None,
        },
    )
    if idempotency_key is not None:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return MemoryMutationResult(replay)
    _assert_unique_name(session, membership, payload.display_name)
    _validate_member_link(session, membership, payload.member_user_id)
    diner = HouseholdDiner(
        household_id=membership.household_id,
        display_name=payload.display_name,
        member_user_id=payload.member_user_id,
        version=1,
    )
    try:
        session.add(diner)
        session.flush()
        record_event(
            session,
            household_id=membership.household_id,
            kind=DomainEventKind.DINER_CREATED,
            actor_user_id=membership.user_id,
            aggregate_type="household_diner",
            aggregate_id=diner.id,
            payload={
                "diner_id": str(diner.id),
                "member_user_id": str(diner.member_user_id) if diner.member_user_id else None,
            },
        )
        result = DinerResponse.model_validate(diner).model_dump(mode="json")
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        session.commit()
    except IntegrityError as exc:
        if _is_member_link_unique_violation(exc):
            session.rollback()
            if idempotency_key is not None:
                replay = _check_receipt(
                    _find_receipt(session, membership, operation, idempotency_key), fingerprint
                )
                if replay is not None:
                    return MemoryMutationResult(replay)
            raise _diner_member_link_conflict() from exc
        replay = _replay_or_conflict(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The diner conflicts with an existing household diner.",
            exc,
        )
        return MemoryMutationResult(replay)
    return MemoryMutationResult(result)


def update_diner(
    session: Session,
    membership: HouseholdMember,
    diner_id: UUID,
    payload: DinerUpdate,
) -> HouseholdDiner:
    diner = _get_diner(session, membership, diner_id, lock=True)
    if diner.version != payload.expected_version:
        raise _conflict(
            "Diner version conflict",
            "The diner changed since it was read. Fetch it again and retry.",
        )
    if "display_name" in payload.model_fields_set:
        assert payload.display_name is not None
        _assert_unique_name(
            session,
            membership,
            payload.display_name,
            exclude_diner_id=diner.id,
        )
    if "member_user_id" in payload.model_fields_set:
        _validate_member_link(
            session,
            membership,
            payload.member_user_id,
            exclude_diner_id=diner.id,
        )
    if "display_name" in payload.model_fields_set:
        assert payload.display_name is not None
        diner.display_name = payload.display_name
    if "member_user_id" in payload.model_fields_set:
        diner.member_user_id = payload.member_user_id
    diner.version += 1
    try:
        record_event(
            session,
            household_id=membership.household_id,
            kind=DomainEventKind.DINER_UPDATED,
            actor_user_id=membership.user_id,
            aggregate_type="household_diner",
            aggregate_id=diner.id,
            payload={
                "diner_id": str(diner.id),
                "member_user_id": str(diner.member_user_id) if diner.member_user_id else None,
            },
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_member_link_unique_violation(exc):
            raise _diner_member_link_conflict() from exc
        raise _conflict(
            "Diner update conflict",
            "The diner conflicts with an existing household diner.",
        ) from exc
    return diner


def archive_diner(session: Session, membership: HouseholdMember, diner_id: UUID) -> None:
    diner = _get_diner(session, membership, diner_id, include_archived=True, lock=True)
    if diner.archived_at is not None:
        return
    diner.archived_at = datetime.now(UTC)
    diner.version += 1
    record_event(
        session,
        household_id=membership.household_id,
        kind=DomainEventKind.DINER_ARCHIVED,
        actor_user_id=membership.user_id,
        aggregate_type="household_diner",
        aggregate_id=diner.id,
        payload={"diner_id": str(diner.id)},
    )
    session.commit()


def _memory_create_fingerprint(
    payload: MemoryCreate, *, requested_diner_name: str | None = None
) -> str:
    if requested_diner_name is None:
        request = {
            "kind": payload.kind.value,
            "content": payload.content,
            "diner_id": str(payload.diner_id) if payload.diner_id else None,
        }
    else:
        request = {
            "kind": payload.kind.value,
            "content": payload.content,
            "diner_name": requested_diner_name.strip().lower(),
            "by": "name",
        }
    return operation_fingerprint("household_memory_create", request)


def replay_memory_create_by_name(
    session: Session,
    membership: HouseholdMember,
    payload: MemoryCreate,
    diner_name: str,
    idempotency_key: str,
) -> MemoryMutationResult | None:
    fingerprint = _memory_create_fingerprint(payload, requested_diner_name=diner_name)
    replay = _check_receipt(
        _find_receipt(session, membership, "household_memory_create", idempotency_key),
        fingerprint,
    )
    return MemoryMutationResult(replay) if replay is not None else None


def create_memory(
    session: Session,
    membership: HouseholdMember,
    payload: MemoryCreate,
    idempotency_key: str | None,
    *,
    requested_diner_name: str | None = None,
) -> MemoryMutationResult:
    operation = "household_memory_create"
    fingerprint = _memory_create_fingerprint(payload, requested_diner_name=requested_diner_name)
    if idempotency_key is not None:
        replay = _check_receipt(
            _find_receipt(session, membership, operation, idempotency_key), fingerprint
        )
        if replay is not None:
            return MemoryMutationResult(replay)
    _validate_memory_diner(session, membership, payload.diner_id)
    memory = HouseholdMemory(
        household_id=membership.household_id,
        diner_id=payload.diner_id,
        kind=payload.kind.value,
        content=payload.content,
        created_by_user_id=membership.user_id,
        version=1,
    )
    try:
        session.add(memory)
        session.flush()
        record_event(
            session,
            household_id=membership.household_id,
            kind=DomainEventKind.MEMORY_CREATED,
            actor_user_id=membership.user_id,
            aggregate_type="household_memory",
            aggregate_id=memory.id,
            payload={
                "memory_id": str(memory.id),
                "diner_id": str(memory.diner_id) if memory.diner_id else None,
                "kind": memory.kind,
            },
        )
        result = MemoryResponse.model_validate(memory).model_dump(mode="json")
        _store_receipt(session, membership, operation, idempotency_key, fingerprint, result)
        session.commit()
    except IntegrityError as exc:
        replay = _replay_or_conflict(
            session,
            membership,
            operation,
            idempotency_key,
            fingerprint,
            "The memory conflicts with the current household state.",
            exc,
        )
        return MemoryMutationResult(replay)
    return MemoryMutationResult(result)


def update_memory(
    session: Session,
    membership: HouseholdMember,
    memory_id: UUID,
    payload: MemoryUpdate,
) -> HouseholdMemory:
    memory = _get_memory(session, membership, memory_id, lock=True)
    if memory.version != payload.expected_version:
        raise _conflict(
            "Memory version conflict",
            "The memory changed since it was read. Fetch it again and retry.",
        )
    if "diner_id" in payload.model_fields_set:
        _validate_memory_diner(session, membership, payload.diner_id)
    if "kind" in payload.model_fields_set:
        assert payload.kind is not None
        memory.kind = payload.kind.value
    if "content" in payload.model_fields_set:
        assert payload.content is not None
        memory.content = payload.content
    if "diner_id" in payload.model_fields_set:
        memory.diner_id = payload.diner_id
    memory.version += 1
    try:
        record_event(
            session,
            household_id=membership.household_id,
            kind=DomainEventKind.MEMORY_UPDATED,
            actor_user_id=membership.user_id,
            aggregate_type="household_memory",
            aggregate_id=memory.id,
            payload={
                "memory_id": str(memory.id),
                "diner_id": str(memory.diner_id) if memory.diner_id else None,
                "kind": memory.kind,
            },
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise _conflict(
            "Memory update conflict", "The memory conflicts with the current household state."
        ) from exc
    return memory


def archive_memory(session: Session, membership: HouseholdMember, memory_id: UUID) -> None:
    memory = _get_memory(session, membership, memory_id, include_archived=True, lock=True)
    if memory.archived_at is not None:
        return
    memory.archived_at = datetime.now(UTC)
    memory.version += 1
    record_event(
        session,
        household_id=membership.household_id,
        kind=DomainEventKind.MEMORY_ARCHIVED,
        actor_user_id=membership.user_id,
        aggregate_type="household_memory",
        aggregate_id=memory.id,
        payload={
            "memory_id": str(memory.id),
            "diner_id": str(memory.diner_id) if memory.diner_id else None,
            "kind": memory.kind,
        },
    )
    session.commit()
