from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uribap_api.domain.identity.policies import (
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
)
from uribap_api.infrastructure.persistence.base import Base
from uribap_api.infrastructure.persistence.identity_models import AppUser


class HouseholdStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class OutboxKind(StrEnum):
    VERIFICATION = "verification"
    PASSWORD_RESET = "password_reset"
    HOUSEHOLD_INVITATION = "household_invitation"


class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Household(Base):
    __tablename__ = "household"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    locale: Mapped[str] = mapped_column(String(32), default="es", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    status: Mapped[HouseholdStatus] = mapped_column(
        Enum(
            HouseholdStatus,
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        default=HouseholdStatus.ACTIVE,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    members: Mapped[list[HouseholdMember]] = relationship(back_populates="household")
    invitations: Mapped[list[HouseholdInvitation]] = relationship(back_populates="household")


class HouseholdMember(Base):
    __tablename__ = "household_member"
    __table_args__ = (
        UniqueConstraint("household_id", "user_id", name="uq_household_member_household_user"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MembershipRole] = mapped_column(
        Enum(
            MembershipRole,
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(
            MembershipStatus,
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        default=MembershipStatus.ACTIVE,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    household: Mapped[Household] = relationship(back_populates="members")
    user: Mapped[AppUser] = relationship(back_populates="memberships")


class HouseholdInvitation(Base):
    __tablename__ = "household_invitation"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_household_invitation_token_hash"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    household_id: Mapped[UUID] = mapped_column(
        ForeignKey("household.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_role: Mapped[MembershipRole] = mapped_column(
        Enum(
            MembershipRole,
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
    )
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(
            InvitationStatus,
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        default=InvitationStatus.PENDING,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invited_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("app_user.id"), nullable=False)
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    household: Mapped[Household] = relationship(back_populates="invitations")


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("app_user.id"), index=True)
    household_id: Mapped[UUID | None] = mapped_column(ForeignKey("household.id"), index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(120))
    target_id: Mapped[UUID | None] = mapped_column()
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailOutboxEntry(Base):
    __tablename__ = "email_outbox_entry"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_email_outbox_dedupe_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[OutboxKind] = mapped_column(
        Enum(
            OutboxKind,
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        nullable=False,
    )
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    template_data: Mapped[dict[str, object]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[OutboxStatus] = mapped_column(
        Enum(
            OutboxStatus,
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        default=OutboxStatus.PENDING,
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
