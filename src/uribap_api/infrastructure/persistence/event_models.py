from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from uribap_api.infrastructure.persistence.base import Base


class DomainEvent(Base):
    __tablename__ = "domain_event"
    __table_args__ = (
        UniqueConstraint("id", "household_id", name="uq_domain_event_household"),
        Index("ix_domain_event_feed", "household_id", "occurred_at"),
        Index("ix_domain_event_kind", "household_id", "kind"),
        CheckConstraint("length(btrim(kind)) > 0", name="ck_domain_event_kind_nonempty"),
        CheckConstraint(
            "length(btrim(aggregate_type)) > 0",
            name="ck_domain_event_aggregate_type_nonempty",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    aggregate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    aggregate_id: Mapped[UUID | None] = mapped_column()
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailDeliveryIntent(Base):
    __tablename__ = "email_delivery_intent"
    __table_args__ = (
        Index("ix_email_delivery_intent_entry", "email_outbox_entry_id", "created_at"),
        CheckConstraint(
            "outcome IN ('sent', 'suppressed', 'failed')",
            name="ck_email_delivery_intent_outcome",
        ),
        CheckConstraint("attempt_number >= 1", name="ck_email_delivery_intent_attempt_positive"),
        CheckConstraint(
            "length(btrim(subject)) > 0",
            name="ck_email_delivery_intent_subject_nonempty",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email_outbox_entry_id: Mapped[UUID] = mapped_column(
        ForeignKey("email_outbox_entry.id", ondelete="CASCADE"), nullable=False
    )
    household_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("household.id", ondelete="SET NULL"), index=True
    )
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
