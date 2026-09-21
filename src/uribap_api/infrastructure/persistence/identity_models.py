from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from uribap_api.domain.identity.policies import UserStatus
from uribap_api.infrastructure.persistence.base import Base

if TYPE_CHECKING:
    from uribap_api.infrastructure.persistence.household_models import HouseholdMember


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(240))
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            native_enum=False,
            values_callable=lambda values: [item.value for item in values],
        ),
        default=UserStatus.ACTIVE,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    identities: Mapped[list[UserIdentity]] = relationship(back_populates="user")
    memberships: Mapped[list[HouseholdMember]] = relationship(back_populates="user")


class UserIdentity(Base):
    __tablename__ = "user_identity"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_user_identity_issuer_subject"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="oidc", nullable=False)
    last_claims_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[AppUser] = relationship(back_populates="identities")
