from datetime import UTC, datetime, timedelta

import pytest

from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.identity.claims import parse_identity_claims, require_scopes


def valid_payload() -> dict[str, object]:
    return {
        "iss": "http://localhost:8080",
        "sub": "user-123",
        "aud": "uribap-api",
        "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
        "scope": "openid profile",
        "email": "person@example.test",
        "email_verified": True,
        "name": "Person",
    }


def test_parse_identity_claims_returns_safe_identity_fields() -> None:
    claims = parse_identity_claims(valid_payload(), expected_issuer="http://localhost:8080")
    assert claims.subject == "user-123"
    assert claims.email == "person@example.test"
    assert claims.email_verified is True
    assert claims.scopes == {"openid", "profile"}


def test_parse_identity_claims_rejects_wrong_issuer_or_expiry() -> None:
    payload = valid_payload()
    payload["iss"] = "https://wrong.example"
    with pytest.raises(DomainError) as error:
        parse_identity_claims(payload, expected_issuer="http://localhost:8080")
    assert error.value.status_code == 401

    expired = valid_payload()
    expired["exp"] = int((datetime.now(UTC) - timedelta(seconds=1)).timestamp())
    with pytest.raises(DomainError):
        parse_identity_claims(expired, expected_issuer="http://localhost:8080")


def test_required_scopes_are_enforced() -> None:
    claims = parse_identity_claims(valid_payload(), expected_issuer="http://localhost:8080")
    with pytest.raises(DomainError) as error:
        require_scopes(claims, {"openid", "api:write"})
    assert error.value.code == "forbidden"
