from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from uribap_api.config import Settings
from uribap_api.domain.events.policies import (
    MAX_DELIVERY_ATTEMPTS,
    DeliveryDecision,
    DomainEventKind,
    build_event,
    decide_delivery,
    next_attempt_delay,
    subject_for,
)
from uribap_api.infrastructure.email.mailer import send_outbox_entry
from uribap_api.infrastructure.logging import get_request_id
from uribap_api.infrastructure.persistence.event_models import (
    DomainEvent,
    EmailDeliveryIntent,
)
from uribap_api.infrastructure.persistence.household_models import (
    EmailOutboxEntry,
    HouseholdInvitation,
    HouseholdMember,
    OutboxStatus,
)


def record_event(
    session: Session,
    *,
    household_id: UUID,
    kind: DomainEventKind,
    actor_user_id: UUID | None,
    aggregate_type: str,
    aggregate_id: UUID | None,
    payload: dict[str, Any] | None = None,
) -> DomainEvent:
    event = build_event(
        kind,
        actor_user_id=actor_user_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        request_id=get_request_id(),
    )
    row = DomainEvent(
        household_id=household_id,
        kind=event.kind.value,
        actor_user_id=event.actor_user_id,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        payload=event.payload,
        request_id=event.request_id,
        occurred_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def list_activity(
    session: Session,
    membership: HouseholdMember,
    *,
    page: int,
    page_size: int,
) -> tuple[list[DomainEvent], bool, dict[str, int]]:
    rows = list(
        session.scalars(
            select(DomainEvent)
            .where(DomainEvent.household_id == membership.household_id)
            .order_by(DomainEvent.occurred_at.desc(), DomainEvent.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size + 1)
        )
    )
    has_more = len(rows) > page_size
    entries = rows[:page_size]

    status_counts = session.execute(
        select(EmailOutboxEntry.status, func.count())
        .join(
            HouseholdInvitation,
            EmailOutboxEntry.dedupe_key
            == func.concat("household-invitation:", HouseholdInvitation.id),
        )
        .where(HouseholdInvitation.household_id == membership.household_id)
        .group_by(EmailOutboxEntry.status)
    ).all()
    summary = {status.value: 0 for status in OutboxStatus}
    for status_value, count in status_counts:
        key = status_value.value if hasattr(status_value, "value") else str(status_value)
        summary[key] = int(count)
    return entries, has_more, summary


@dataclass(frozen=True)
class DispatchResult:
    claimed: int
    suppressed: int
    sent: int
    failed: int


def _write_intent(
    session: Session,
    entry: EmailOutboxEntry,
    *,
    outcome: str,
    detail: str | None,
    attempt_number: int,
    household_id: UUID | None,
) -> None:
    session.add(
        EmailDeliveryIntent(
            email_outbox_entry_id=entry.id,
            household_id=household_id,
            outcome=outcome,
            subject=subject_for(entry.kind.value),
            detail=detail,
            attempt_number=attempt_number,
        )
    )


def _intent_household_id(session: Session, entry: EmailOutboxEntry) -> UUID | None:
    if not entry.dedupe_key.startswith("household-invitation:"):
        return None
    return session.scalar(
        select(HouseholdInvitation.household_id).where(
            func.concat("household-invitation:", HouseholdInvitation.id) == entry.dedupe_key
        )
    )


def process_outbox(
    session: Session,
    settings: Settings,
    *,
    limit: int = 50,
) -> DispatchResult:
    now = datetime.now(UTC)
    claimed = list(
        session.scalars(
            select(EmailOutboxEntry)
            .where(
                EmailOutboxEntry.status == OutboxStatus.PENDING,
                EmailOutboxEntry.available_at <= now,
            )
            .order_by(EmailOutboxEntry.created_at.asc(), EmailOutboxEntry.id.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    suppressed = sent = failed = 0
    for entry in claimed:
        entry.attempts += 1
        household_id = _intent_household_id(session, entry)
        decision = decide_delivery(delivery_enabled=settings.email_delivery_enabled)
        if decision is DeliveryDecision.SUPPRESSED:
            entry.status = OutboxStatus.SUPPRESSED
            _write_intent(
                session,
                entry,
                outcome=OutboxStatus.SUPPRESSED.value,
                detail="Email delivery disabled for this environment.",
                attempt_number=entry.attempts,
                household_id=household_id,
            )
            suppressed += 1
            continue
        try:
            send_outbox_entry(settings, entry)
        except Exception as exc:  # noqa: BLE001 — recorded, never raised
            if entry.attempts >= MAX_DELIVERY_ATTEMPTS:
                entry.status = OutboxStatus.FAILED
                failed += 1
                outcome = OutboxStatus.FAILED.value
            else:
                entry.available_at = now + next_attempt_delay(entry.attempts)
                outcome = "failed"
            entry.last_error = str(exc)[:500]
            _write_intent(
                session,
                entry,
                outcome=outcome,
                detail=str(exc)[:500],
                attempt_number=entry.attempts,
                household_id=household_id,
            )
            continue
        entry.status = OutboxStatus.SENT
        entry.sent_at = now
        _write_intent(
            session,
            entry,
            outcome=OutboxStatus.SENT.value,
            detail=None,
            attempt_number=entry.attempts,
            household_id=household_id,
        )
        sent += 1
    session.commit()
    return DispatchResult(claimed=len(claimed), suppressed=suppressed, sent=sent, failed=failed)
