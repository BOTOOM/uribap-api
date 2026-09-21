from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.infrastructure.persistence.household_models import (
    EmailOutboxEntry,
    OutboxKind,
    OutboxStatus,
)


def queue_email(
    session: Session,
    *,
    dedupe_key: str,
    kind: OutboxKind,
    recipient_email: str,
    template_data: dict[str, object],
) -> EmailOutboxEntry:
    existing = session.scalar(
        select(EmailOutboxEntry).where(EmailOutboxEntry.dedupe_key == dedupe_key)
    )
    if existing is not None:
        return existing
    entry = EmailOutboxEntry(
        dedupe_key=dedupe_key,
        kind=kind,
        recipient_email=recipient_email,
        template_data=template_data,
    )
    session.add(entry)
    session.flush()
    return entry


def mark_sent(session: Session, entry_id: UUID) -> None:
    entry = session.get(EmailOutboxEntry, entry_id)
    if entry is not None:
        entry.status = OutboxStatus.SENT
        entry.sent_at = datetime.now(UTC)
        entry.attempts += 1


def mark_failed(session: Session, entry_id: UUID, detail: str) -> None:
    entry = session.get(EmailOutboxEntry, entry_id)
    if entry is not None:
        entry.status = OutboxStatus.FAILED
        entry.last_error = detail[:500]
        entry.attempts += 1
