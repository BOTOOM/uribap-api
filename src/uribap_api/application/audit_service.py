from uuid import UUID

from sqlalchemy.orm import Session

from uribap_api.infrastructure.persistence.household_models import AuditEvent


def record_audit(
    session: Session,
    *,
    actor_user_id: UUID | None,
    household_id: UUID | None,
    action: str,
    request_id: str,
    target_type: str | None = None,
    target_id: UUID | None = None,
    metadata: dict[str, object] | None = None,
) -> AuditEvent:
    safe_metadata = {
        key: value
        for key, value in (metadata or {}).items()
        if key.casefold() not in {"authorization", "cookie", "token", "secret", "password"}
    }
    event = AuditEvent(
        actor_user_id=actor_user_id,
        household_id=household_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        request_id=request_id,
        metadata_json=safe_metadata,
    )
    session.add(event)
    session.flush()
    return event
