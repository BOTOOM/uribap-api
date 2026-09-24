from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from uribap_api.config import Settings
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.identity.jwt_validator import TokenValidator


@pytest.fixture(scope="module")
def signing_keys() -> tuple[Any, Any, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key(), wrong_private_key


def settings(
    *,
    userinfo_url: str = "https://issuer.example.test/oidc/v1/userinfo",
    required_scopes: str = "openid profile",
) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "environment": "test",
        "oidc_issuer": "https://issuer.example.test",
        "oidc_audience": "uribap-api",
        "oidc_jwks_url": "https://issuer.example.test/oauth/v2/keys",
        "oidc_userinfo_url": userinfo_url,
        "oidc_required_scopes": required_scopes,
        "oidc_clock_skew_seconds": 0,
    }
    return Settings(**values)


def signed_token(
    private_key: Any, *, include_scope: bool = True, **overrides: Any
) -> str:
    payload: dict[str, Any] = {
        "iss": "https://issuer.example.test",
        "sub": "user-123",
        "aud": "uribap-api",
        "exp": int((datetime.now(UTC) + timedelta(minutes=5)).timestamp()),
    }
    if include_scope:
        payload["scope"] = "openid profile"
    payload.update(overrides)
    return jwt.encode(payload, private_key, algorithm="RS256")


def configured_validator(
    public_key: Any, *, required_scopes: str = "openid profile"
) -> TokenValidator:
    validator = TokenValidator(settings(required_scopes=required_scopes))
    validator.cache.get_key = AsyncMock(return_value=public_key)
    return validator


@pytest.mark.asyncio
async def test_valid_jwt_is_enriched_with_matching_userinfo_profile(
    signing_keys: tuple[Any, Any, Any],
) -> None:
    private_key, public_key, _ = signing_keys
    validator = configured_validator(public_key)
    assert validator.userinfo is not None
    validator.userinfo.get_profile = AsyncMock(
        return_value={
            "email": "person@example.test",
            "email_verified": True,
            "name": "Person",
            "preferred_username": "person",
        }
    )

    token = signed_token(private_key)
    claims = await validator.validate(token)

    assert claims.subject == "user-123"
    assert claims.email == "person@example.test"
    assert claims.email_verified is True
    assert claims.display_name == "Person"
    validator.userinfo.get_profile.assert_awaited_once_with(token, subject="user-123")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token_kwargs", "sign_with_wrong_key", "required_scopes", "status_code"),
    [
        ({}, True, "openid profile", 401),
        ({"iss": "https://other.example.test"}, False, "openid profile", 401),
        ({"aud": "other-api"}, False, "openid profile", 401),
        (
            {"exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())},
            False,
            "openid profile",
            401,
        ),
        ({"scope": "openid"}, False, "openid profile", 403),
    ],
)
async def test_rejected_jwt_never_calls_userinfo(
    signing_keys: tuple[Any, Any, Any],
    token_kwargs: dict[str, Any],
    sign_with_wrong_key: bool,
    required_scopes: str,
    status_code: int,
) -> None:
    private_key, public_key, wrong_private_key = signing_keys
    validator = configured_validator(public_key)
    assert validator.userinfo is not None
    userinfo_request = AsyncMock()
    validator.userinfo.get_profile = userinfo_request
    validator.settings.oidc_required_scopes = required_scopes
    signing_key = wrong_private_key if sign_with_wrong_key else private_key

    with pytest.raises(DomainError) as error:
        await validator.validate(signed_token(signing_key, **token_kwargs))

    assert error.value.status_code == status_code
    userinfo_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_zitadel_jwt_without_scope_uses_empty_optional_scope_policy(
    signing_keys: tuple[Any, Any, Any],
) -> None:
    private_key, public_key, _ = signing_keys
    validator = configured_validator(public_key, required_scopes="")
    assert validator.userinfo is not None
    validator.userinfo.get_profile = AsyncMock(
        return_value={
            "email": "person@example.test",
            "email_verified": True,
            "name": "Person",
            "preferred_username": None,
        }
    )
    token = signed_token(private_key, include_scope=False)

    claims = await validator.validate(token)

    assert "scope" not in claims.raw
    assert claims.email_verified is True
    validator.userinfo.get_profile.assert_awaited_once_with(token, subject="user-123")


@pytest.mark.asyncio
async def test_zitadel_jwt_without_scope_still_enforces_configured_scope_before_userinfo(
    signing_keys: tuple[Any, Any, Any],
) -> None:
    private_key, public_key, _ = signing_keys
    validator = configured_validator(public_key, required_scopes="openid")
    assert validator.userinfo is not None
    userinfo_request = AsyncMock()
    validator.userinfo.get_profile = userinfo_request

    with pytest.raises(DomainError) as error:
        await validator.validate(signed_token(private_key, include_scope=False))

    assert error.value.status_code == 403
    userinfo_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_jwt_only_validation_remains_unchanged(
    signing_keys: tuple[Any, Any, Any],
) -> None:
    private_key, public_key, _ = signing_keys
    validator = TokenValidator(settings(userinfo_url=""))
    validator.cache.get_key = AsyncMock(return_value=public_key)

    claims = await validator.validate(
        signed_token(
            private_key,
            email="person@example.test",
            email_verified=True,
            name="Person",
        )
    )

    assert validator.userinfo is None
    assert claims.email == "person@example.test"
    assert claims.email_verified is True


@pytest.mark.asyncio
async def test_userinfo_profile_cannot_replace_authorization_claims(
    signing_keys: tuple[Any, Any, Any],
) -> None:
    private_key, public_key, _ = signing_keys
    validator = configured_validator(public_key)
    assert validator.userinfo is not None
    validator.userinfo.get_profile = AsyncMock(
        return_value={
            "email": "person@example.test",
            "email_verified": False,
            "name": "Person",
            "preferred_username": None,
        }
    )

    claims = await validator.validate(
        signed_token(private_key, scope="openid profile", aud="uribap-api")
    )

    assert claims.raw["iss"] == "https://issuer.example.test"
    assert claims.raw["sub"] == "user-123"
    assert claims.raw["aud"] == "uribap-api"
    assert claims.raw["scope"] == "openid profile"
    assert claims.email_verified is False
