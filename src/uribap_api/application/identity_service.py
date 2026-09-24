from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from uribap_api.domain.identity.policies import UserStatus, normalize_email
from uribap_api.infrastructure.identity.claims import IdentityClaims
from uribap_api.infrastructure.persistence.identity_models import AppUser, UserIdentity


def provision_user(session: Session, claims: IdentityClaims) -> AppUser:
    identity = session.scalar(
        select(UserIdentity)
        .where(UserIdentity.issuer == claims.issuer, UserIdentity.subject == claims.subject)
        .with_for_update()
    )
    email = None
    if claims.email:
        try:
            email = normalize_email(claims.email)
        except ValueError:
            email = None
    email_verified = email is not None and claims.email_verified
    now = datetime.now(UTC)
    if identity is not None:
        user = identity.user
        if user.status == UserStatus.DISABLED:
            return user
        user.email = email or user.email
        user.email_verified = email_verified
        user.display_name = claims.display_name or user.display_name
        user.last_seen_at = now
        identity.last_claims_at = now
        session.commit()
        session.refresh(user)
        return user

    user = AppUser(
        email=email,
        email_verified=email_verified,
        display_name=claims.display_name,
        last_seen_at=now,
    )
    session.add(user)
    session.flush()
    session.add(
        UserIdentity(
            user_id=user.id,
            issuer=claims.issuer,
            subject=claims.subject,
            provider="oidc",
            last_claims_at=now,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(UserIdentity)
            .where(UserIdentity.issuer == claims.issuer, UserIdentity.subject == claims.subject)
            .with_for_update()
        )
        if existing is None:
            raise
        return provision_user(session, claims)
    session.refresh(user)
    return user
