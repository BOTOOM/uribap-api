from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from uribap_api.api.dependencies import get_current_user, get_session, get_user_directory
from uribap_api.api.schemas import InvitationCreate
from uribap_api.application.invitation_service import create_invitation
from uribap_api.domain.events.policies import DomainEventKind
from uribap_api.domain.identity.policies import (
    InvitationStatus,
    MembershipRole,
    MembershipStatus,
    create_invitation_token,
)
from uribap_api.infrastructure.identity.zitadel_users import ZitadelDirectoryError
from uribap_api.infrastructure.persistence.event_models import DomainEvent
from uribap_api.infrastructure.persistence.household_models import (
    AuditEvent,
    EmailOutboxEntry,
    Household,
    HouseholdInvitation,
    HouseholdMember,
    OutboxStatus,
)
from uribap_api.infrastructure.persistence.identity_models import AppUser
from uribap_api.main import app

pytestmark = pytest.mark.integration


class StubDirectory:
    def __init__(self, user_id: str | None = None, *, fail: bool = False) -> None:
        self.user_id = user_id
        self.fail = fail
        self.find_calls: list[str] = []
        self.create_calls: list[tuple[str, str | None]] = []
        self.invite_calls: list[str] = []

    def find_user_id_by_email(self, email: str) -> str | None:
        self.find_calls.append(email)
        if self.fail:
            raise ZitadelDirectoryError(status_code=503)
        return self.user_id

    def create_human_user(self, email: str, display_name: str | None) -> str:
        self.create_calls.append((email, display_name))
        return "created-user-123"

    def send_invite_code(self, user_id: str) -> None:
        self.invite_calls.append(user_id)


@pytest.fixture
def invitation_client(integration_engine) -> Generator[tuple[TestClient, UUID, dict[str, AppUser]]]:
    household_id = uuid4()
    owner_id = uuid4()
    owner_email = f"owner-{owner_id}@example.test"
    owner = AppUser(
        id=owner_id,
        email=owner_email,
        email_verified=True,
        display_name="Household Owner",
    )
    principal = {"user": owner}
    with Session(integration_engine) as session:
        session.add_all(
            [
                AppUser(
                    id=owner_id,
                    email=owner_email,
                    email_verified=True,
                    display_name="Household Owner",
                ),
                Household(
                    id=household_id,
                    name="Invitation Test Household",
                    locale="es",
                    timezone="UTC",
                ),
            ]
        )
        session.flush()
        session.add(
            HouseholdMember(
                household_id=household_id,
                user_id=owner_id,
                role=MembershipRole.OWNER,
                status=MembershipStatus.ACTIVE,
            )
        )
        session.commit()

    def override_session() -> Generator[Session]:
        with Session(integration_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = lambda: principal["user"]
    app.dependency_overrides[get_user_directory] = lambda: None
    try:
        with TestClient(app) as client:
            yield client, household_id, principal
    finally:
        app.dependency_overrides.clear()


def create_pending_invitation(
    integration_engine,
    household_id: UUID,
    owner_id: UUID,
    email: str,
    *,
    expires_in_hours: int = 72,
) -> HouseholdInvitation:
    with Session(integration_engine) as session:
        inviter = session.scalar(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == owner_id,
            )
        )
        assert inviter is not None
        invitation, _, _ = create_invitation(
            session,
            household_id=household_id,
            inviter=inviter,
            payload=InvitationCreate(email=email, expires_in_hours=expires_in_hours),
            request_id="req-pending-invitation-test",
        )
        return invitation


def insert_invitation(
    integration_engine,
    household_id: UUID,
    owner_id: UUID,
    email: str,
    *,
    status: InvitationStatus = InvitationStatus.PENDING,
    expires_at: datetime | None = None,
) -> HouseholdInvitation:
    token = create_invitation_token()
    invitation = HouseholdInvitation(
        household_id=household_id,
        invited_email=email,
        token_hash=token.digest,
        requested_role=MembershipRole.MEMBER,
        status=status,
        expires_at=expires_at or datetime.now(UTC) + timedelta(hours=72),
        invited_by_user_id=owner_id,
    )
    with Session(integration_engine) as session:
        session.add(invitation)
        session.commit()
        session.refresh(invitation)
        return invitation


def get_outbox_entry(integration_engine, email: str) -> EmailOutboxEntry:
    with Session(integration_engine) as session:
        entry = session.scalar(
            select(EmailOutboxEntry).where(EmailOutboxEntry.recipient_email == email)
        )
        assert entry is not None
        return entry


def test_new_zitadel_user_receives_invite_without_smtp(
    invitation_client, integration_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, household_id, _ = invitation_client
    email = f"new-{uuid4()}@example.test"
    directory = StubDirectory()
    app.dependency_overrides[get_user_directory] = lambda: directory

    def fail_smtp(*args, **kwargs) -> None:
        raise AssertionError("SMTP must not be used in ZITADEL mode")

    monkeypatch.setattr("uribap_api.api.invitations.send_outbox_entry", fail_smtp)

    response = client.post(
        f"/api/v1/households/{household_id}/invitations",
        json={"email": email, "display_name": "Ada Lovelace"},
    )

    assert response.status_code == 202
    assert response.json()["delivery"] == "zitadel_invite"
    assert directory.find_calls == [email]
    assert directory.create_calls == [(email, "Ada Lovelace")]
    assert directory.invite_calls == ["created-user-123"]
    assert get_outbox_entry(integration_engine, email).status == OutboxStatus.SENT


def test_existing_zitadel_user_is_suppressed_without_smtp(
    invitation_client, integration_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, household_id, _ = invitation_client
    email = f"existing-{uuid4()}@example.test"
    directory = StubDirectory("existing-user-123")
    app.dependency_overrides[get_user_directory] = lambda: directory
    monkeypatch.setattr(
        "uribap_api.api.invitations.send_outbox_entry",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("SMTP must not be used in ZITADEL mode")
        ),
    )

    response = client.post(
        f"/api/v1/households/{household_id}/invitations",
        json={"email": email, "role": "member"},
    )

    assert response.status_code == 202
    assert response.json()["delivery"] == "existing_account"
    assert directory.create_calls == []
    assert directory.invite_calls == []
    assert get_outbox_entry(integration_engine, email).status == OutboxStatus.SUPPRESSED


def test_zitadel_error_retains_invitation_and_records_safe_failure(
    invitation_client,
    integration_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, household_id, _ = invitation_client
    email = f"failed-{uuid4()}@example.test"
    directory = StubDirectory(fail=True)
    app.dependency_overrides[get_user_directory] = lambda: directory
    warning_calls: list[tuple[str, tuple[object, ...]]] = []
    monkeypatch.setattr(
        "uribap_api.api.invitations.logger.warning",
        lambda message, *args: warning_calls.append((message, args)),
    )
    monkeypatch.setattr(
        "uribap_api.api.invitations.send_outbox_entry",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("SMTP must not be used in ZITADEL mode")
        ),
    )

    response = client.post(
        f"/api/v1/households/{household_id}/invitations",
        json={"email": email},
    )

    assert response.status_code == 202
    assert response.json()["delivery"] == "failed"
    entry = get_outbox_entry(integration_engine, email)
    assert entry.status == OutboxStatus.FAILED
    assert entry.last_error == "zitadel invite failed"
    with Session(integration_engine) as session:
        invitation = session.scalar(
            select(HouseholdInvitation).where(HouseholdInvitation.invited_email == email)
        )
        assert invitation is not None
        assert invitation.status == InvitationStatus.PENDING
    assert len(warning_calls) == 1
    message, values = warning_calls[0]
    assert message == "ZITADEL invitation delivery failed status_code=%s request_id=%s"
    assert values[0] == 503
    assert str(values[1]).startswith("req_")
    assert email not in message
    assert email not in str(values)
    assert "synthetic-service-token" not in str(values)


def test_failed_invitation_can_be_retried_before_user_creation(
    invitation_client, integration_engine
) -> None:
    client, household_id, _ = invitation_client
    email = f"retry-before-create-{uuid4()}@example.test"
    directory = StubDirectory(fail=True)
    app.dependency_overrides[get_user_directory] = lambda: directory

    first = client.post(
        f"/api/v1/households/{household_id}/invitations",
        json={"email": email, "role": "member", "expires_in_hours": 1},
    )
    assert first.status_code == 202
    assert first.json()["delivery"] == "failed"
    first_invitation = first.json()
    first_outbox = get_outbox_entry(integration_engine, email)
    first_token_hash: str
    with Session(integration_engine) as session:
        invitation = session.scalar(
            select(HouseholdInvitation).where(HouseholdInvitation.invited_email == email)
        )
        assert invitation is not None
        first_token_hash = invitation.token_hash
        first_expiry = invitation.expires_at
        first_invitation_id = invitation.id

    directory.fail = False
    retry = client.post(
        f"/api/v1/households/{household_id}/invitations",
        json={"email": email, "role": "admin", "expires_in_hours": 72},
    )

    assert retry.status_code == 202
    assert retry.json()["id"] == first_invitation["id"]
    assert retry.json()["delivery"] == "zitadel_invite"
    assert directory.create_calls == [(email, None)]
    assert directory.invite_calls == ["created-user-123"]
    with Session(integration_engine) as session:
        invitation = session.scalar(
            select(HouseholdInvitation).where(HouseholdInvitation.invited_email == email)
        )
        assert invitation is not None
        assert invitation.id == first_invitation_id
        assert invitation.token_hash != first_token_hash
        assert invitation.expires_at > first_expiry
        assert invitation.requested_role == MembershipRole.ADMIN
        outbox = session.scalar(
            select(EmailOutboxEntry).where(EmailOutboxEntry.recipient_email == email)
        )
        assert outbox is not None
        assert outbox.id == first_outbox.id
        assert outbox.status == OutboxStatus.SENT
        events = list(
            session.scalars(select(DomainEvent).where(DomainEvent.aggregate_id == invitation.id))
        )
        assert sum(event.kind == DomainEventKind.INVITATION_CREATED.value for event in events) == 1
        audits = list(
            session.scalars(select(AuditEvent).where(AuditEvent.target_id == invitation.id))
        )
        assert {event.action for event in audits} == {
            "invitation.created",
            "invitation.redelivered",
        }


def test_failed_invitation_can_be_retried_after_user_creation(
    invitation_client, integration_engine
) -> None:
    class FailFirstInviteDirectory(StubDirectory):
        def __init__(self) -> None:
            super().__init__()
            self.fail_invite = True
            self.persisted_before_send = False

        def send_invite_code(self, user_id: str) -> None:
            with Session(integration_engine) as session:
                entry = session.scalar(
                    select(EmailOutboxEntry).where(EmailOutboxEntry.recipient_email == email)
                )
                self.persisted_before_send = (
                    entry is not None and entry.template_data.get("zitadel_user_id") == user_id
                )
            super().send_invite_code(user_id)
            if self.fail_invite:
                raise ZitadelDirectoryError(status_code=503)

    client, household_id, _ = invitation_client
    email = f"retry-after-create-{uuid4()}@example.test"
    directory = FailFirstInviteDirectory()
    app.dependency_overrides[get_user_directory] = lambda: directory

    first = client.post(
        f"/api/v1/households/{household_id}/invitations",
        json={"email": email},
    )
    assert first.status_code == 202
    assert first.json()["delivery"] == "failed"
    assert directory.persisted_before_send
    entry = get_outbox_entry(integration_engine, email)
    assert entry.template_data["zitadel_user_id"] == "created-user-123"

    directory.user_id = "created-user-123"
    directory.fail_invite = False
    retry = client.post(
        f"/api/v1/households/{household_id}/invitations",
        json={"email": email},
    )

    assert retry.status_code == 202
    assert retry.json()["id"] == first.json()["id"]
    assert retry.json()["delivery"] == "zitadel_invite"
    assert directory.find_calls == [email, email]
    assert directory.create_calls == [(email, None)]
    assert directory.invite_calls == ["created-user-123", "created-user-123"]
    assert get_outbox_entry(integration_engine, email).status == OutboxStatus.SENT


def test_non_failed_pending_invitation_cannot_be_retried(
    invitation_client, integration_engine
) -> None:
    client, household_id, _ = invitation_client
    email = f"not-retryable-{uuid4()}@example.test"
    directory = StubDirectory("existing-user-123")
    app.dependency_overrides[get_user_directory] = lambda: directory
    payload = {"email": email}

    first = client.post(f"/api/v1/households/{household_id}/invitations", json=payload)
    second = client.post(f"/api/v1/households/{household_id}/invitations", json=payload)

    assert first.status_code == 202
    assert second.status_code == 409
    assert directory.find_calls == [email]
    assert get_outbox_entry(integration_engine, email).status == OutboxStatus.SUPPRESSED


def test_smtp_fallback_returns_email_on_success(
    invitation_client, integration_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, household_id, _ = invitation_client
    email = f"smtp-{uuid4()}@example.test"
    sent: list[tuple[tuple[object, ...], dict[str, object]]] = []
    monkeypatch.setattr(
        "uribap_api.api.invitations.send_outbox_entry",
        lambda *args, **kwargs: sent.append((args, kwargs)),
    )

    response = client.post(
        f"/api/v1/households/{household_id}/invitations",
        json={"email": email},
    )

    assert response.status_code == 202
    assert response.json()["delivery"] == "email"
    assert len(sent) == 1
    assert get_outbox_entry(integration_engine, email).status == OutboxStatus.SENT


def test_smtp_fallback_returns_failed_when_sending_raises(
    invitation_client, integration_engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, household_id, _ = invitation_client
    email = f"smtp-failed-{uuid4()}@example.test"

    def fail_smtp(*args, **kwargs) -> None:
        raise RuntimeError("synthetic SMTP failure")

    monkeypatch.setattr("uribap_api.api.invitations.send_outbox_entry", fail_smtp)

    response = client.post(
        f"/api/v1/households/{household_id}/invitations",
        json={"email": email},
    )

    assert response.status_code == 202
    assert response.json()["delivery"] == "failed"
    entry = get_outbox_entry(integration_engine, email)
    assert entry.status == OutboxStatus.FAILED
    assert entry.last_error == "smtp delivery failed"


def test_pending_invitation_list_filters_email_status_and_expiry(
    invitation_client, integration_engine
) -> None:
    client, household_id, principal = invitation_client
    owner = principal["user"]
    invitee_id = uuid4()
    invitee_email = f"invitee-{invitee_id}@example.test"
    with Session(integration_engine) as session:
        session.add(
            AppUser(
                id=invitee_id,
                email=invitee_email,
                email_verified=True,
                display_name="Invited Person",
            )
        )
        session.commit()

    expected = create_pending_invitation(
        integration_engine,
        household_id,
        owner.id,
        invitee_email.upper(),
    )
    create_pending_invitation(
        integration_engine, household_id, owner.id, f"other-{uuid4()}@example.test"
    )
    expired = create_pending_invitation(
        integration_engine,
        household_id,
        owner.id,
        f"expired-{uuid4()}@example.test",
        expires_in_hours=1,
    )
    with Session(integration_engine) as session:
        expired_row = session.get(HouseholdInvitation, expired.id)
        assert expired_row is not None
        expired_row.expires_at = datetime.now(UTC) - timedelta(hours=1)
        session.commit()
    insert_invitation(
        integration_engine,
        household_id,
        owner.id,
        invitee_email,
        status=InvitationStatus.ACCEPTED,
    )

    principal["user"] = AppUser(
        id=invitee_id,
        email=invitee_email,
        email_verified=True,
        display_name="Invited Person",
    )
    response = client.get("/api/v1/me/invitations")

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": str(expected.id),
            "household_id": str(household_id),
            "household_name": "Invitation Test Household",
            "requested_role": "member",
            "expires_at": expected.expires_at.isoformat().replace("+00:00", "Z"),
            "invited_by_display_name": "Household Owner",
        }
    ]


def test_pending_list_is_empty_for_unverified_email(invitation_client) -> None:
    client, _, principal = invitation_client
    principal["user"] = AppUser(
        id=uuid4(),
        email="unverified@example.test",
        email_verified=False,
        display_name="Unverified",
    )

    response = client.get("/api/v1/me/invitations")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_pending_list_is_empty_without_email(invitation_client) -> None:
    client, _, principal = invitation_client
    principal["user"] = AppUser(id=uuid4(), email=None, email_verified=True)

    response = client.get("/api/v1/me/invitations")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_accept_by_id_creates_membership_and_preserves_acceptance_events(
    invitation_client, integration_engine
) -> None:
    client, household_id, principal = invitation_client
    owner = principal["user"]
    invitee_id = uuid4()
    invitee_email = f"invitee-{invitee_id}@example.test"
    with Session(integration_engine) as session:
        session.add(
            AppUser(
                id=invitee_id,
                email=invitee_email,
                email_verified=True,
                display_name="Invited Person",
            )
        )
        session.commit()
    invitation = create_pending_invitation(
        integration_engine, household_id, owner.id, invitee_email
    )
    principal["user"] = AppUser(
        id=invitee_id,
        email=invitee_email,
        email_verified=True,
        display_name="Invited Person",
    )

    response = client.post(f"/api/v1/me/invitations/{invitation.id}/accept")

    assert response.status_code == 200
    assert response.json()["role"] == "member"
    with Session(integration_engine) as session:
        member = session.scalar(
            select(HouseholdMember).where(
                HouseholdMember.household_id == household_id,
                HouseholdMember.user_id == invitee_id,
            )
        )
        stored_invitation = session.get(HouseholdInvitation, invitation.id)
        assert member is not None
        assert member.status == MembershipStatus.ACTIVE
        assert stored_invitation is not None
        assert stored_invitation.status == InvitationStatus.ACCEPTED
        assert session.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "invitation.accepted",
                AuditEvent.target_id == invitation.id,
            )
        )
        event_kinds = set(
            session.scalars(
                select(DomainEvent.kind).where(
                    DomainEvent.aggregate_id.in_([invitation.id, member.id])
                )
            )
        )
        assert event_kinds == {
            "invitation.created",
            "invitation.accepted",
            "household.member_added",
        }


def test_accept_by_id_hides_invitations_for_other_emails(
    invitation_client, integration_engine
) -> None:
    client, household_id, principal = invitation_client
    owner = principal["user"]
    invitation = create_pending_invitation(
        integration_engine,
        household_id,
        owner.id,
        f"someone-else-{uuid4()}@example.test",
    )
    principal["user"] = AppUser(
        id=uuid4(),
        email=f"other-user-{uuid4()}@example.test",
        email_verified=True,
        display_name="Other",
    )

    response = client.post(f"/api/v1/me/invitations/{invitation.id}/accept")

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_accept_by_id_requires_verified_email(invitation_client) -> None:
    client, _, principal = invitation_client
    invitation_id = uuid4()
    principal["user"] = AppUser(
        id=uuid4(),
        email="unverified@example.test",
        email_verified=False,
        display_name="Unverified",
    )

    response = client.post(f"/api/v1/me/invitations/{invitation_id}/accept")

    assert response.status_code == 403
    assert response.json()["detail"] == "A verified email is required."


def test_accept_by_id_preserves_expiry_error(invitation_client, integration_engine) -> None:
    client, household_id, principal = invitation_client
    owner = principal["user"]
    invitee_id = uuid4()
    invitee_email = f"expired-{invitee_id}@example.test"
    with Session(integration_engine) as session:
        session.add(AppUser(id=invitee_id, email=invitee_email, email_verified=True))
        session.commit()
    invitation = insert_invitation(
        integration_engine,
        household_id,
        owner.id,
        invitee_email,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    principal["user"] = AppUser(id=invitee_id, email=invitee_email, email_verified=True)

    response = client.post(f"/api/v1/me/invitations/{invitation.id}/accept")

    assert response.status_code == 400
    assert response.json()["code"] == "invitation_expired"


def test_accept_by_id_preserves_already_member_error(invitation_client, integration_engine) -> None:
    client, household_id, principal = invitation_client
    owner = principal["user"]
    assert owner.email is not None
    invitation = insert_invitation(
        integration_engine,
        household_id,
        owner.id,
        owner.email,
    )

    response = client.post(f"/api/v1/me/invitations/{invitation.id}/accept")

    assert response.status_code == 409
    assert response.json()["code"] == "invitation_consumed"
