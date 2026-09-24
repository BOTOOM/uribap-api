from collections.abc import Callable
from typing import Any

import httpx
import pytest

from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.identity.userinfo import UserInfoClient

Handler = Callable[[httpx.Request], httpx.Response]


def install_transport(
    monkeypatch: pytest.MonkeyPatch, handler: Handler
) -> tuple[list[httpx.Request], list[dict[str, Any]]]:
    requests: list[httpx.Request] = []
    client_options: list[dict[str, Any]] = []
    original_client = httpx.AsyncClient

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    def create_client(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        client_options.append(kwargs.copy())
        kwargs["transport"] = httpx.MockTransport(handle)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", create_client)
    return requests, client_options


def profile_response(profile: object) -> httpx.Response:
    return httpx.Response(200, json=profile)


@pytest.mark.asyncio
async def test_get_profile_returns_only_allowed_fields_for_matching_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = {
        "sub": "user-123",
        "email": "person@example.test",
        "email_verified": True,
        "name": "Person",
        "preferred_username": "person",
        "iss": "https://attacker.example.test",
        "aud": "attacker-client",
        "scope": "admin",
        "exp": 1,
    }
    requests, _ = install_transport(
        monkeypatch, lambda request: profile_response(profile)
    )

    result = await UserInfoClient("https://issuer.example.test/oidc/v1/userinfo").get_profile(
        "synthetic-access-token", subject="user-123"
    )

    assert result == {
        "email": "person@example.test",
        "email_verified": True,
        "name": "Person",
        "preferred_username": "person",
    }
    assert len(requests) == 1
    assert requests[0].headers["Authorization"] == "Bearer synthetic-access-token"
    assert requests[0].headers["Accept"] == "application/json"


@pytest.mark.asyncio
async def test_connect_host_preserves_original_public_host_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests, _ = install_transport(
        monkeypatch,
        lambda request: profile_response({"sub": "user-123", "email": "person@example.test"}),
    )
    client = UserInfoClient(
        "http://localhost:8080/oidc/v1/userinfo",
        connect_host="host.docker.internal",
    )

    profile = await client.get_profile("synthetic-token", subject="user-123")

    assert profile["email"] == "person@example.test"
    assert requests[0].url.scheme == "http"
    assert requests[0].url.host == "host.docker.internal"
    assert requests[0].url.port == 8080
    assert requests[0].url.path == "/oidc/v1/userinfo"
    assert requests[0].headers["Host"] == "localhost:8080"
    assert requests[0].headers["Authorization"] == "Bearer synthetic-token"


@pytest.mark.asyncio
async def test_get_profile_normalizes_email_before_returning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_transport(
        monkeypatch,
        lambda request: profile_response(
            {"sub": "user-123", "email": "  PERSON@Example.Test  ", "email_verified": True}
        ),
    )

    result = await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
        "synthetic-token", subject="user-123"
    )

    assert result["email"] == "person@example.test"
    assert result["email_verified"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("email", ["not-an-email", "", "person@invalid", "   "])
async def test_get_profile_rejects_invalid_email_redacted(
    monkeypatch: pytest.MonkeyPatch, email: str
) -> None:
    install_transport(
        monkeypatch,
        lambda request: profile_response(
            {"sub": "user-123", "email": email, "email_verified": True}
        ),
    )

    with pytest.raises(DomainError) as error:
        await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
            "synthetic-token", subject="user-123"
        )

    assert error.value.code == "identity_provider_unavailable"
    assert error.value.status_code == 503
    if email:
        assert email not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("email", "email_verified", "expected_verified"),
    [
        ("person@example.test", False, False),
        ("person@example.test", None, False),
        (None, True, False),
        (None, None, False),
    ],
)
async def test_get_profile_never_upgrades_missing_or_false_verification(
    monkeypatch: pytest.MonkeyPatch,
    email: str | None,
    email_verified: bool | None,
    expected_verified: bool,
) -> None:
    profile: dict[str, Any] = {"sub": "user-123", "email": email}
    if email_verified is not None:
        profile["email_verified"] = email_verified
    install_transport(monkeypatch, lambda request: profile_response(profile))

    result = await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
        "synthetic-token", subject="user-123"
    )

    assert result["email_verified"] is expected_verified


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "profile",
    [
        {"sub": "user-123", "email_verified": 1},
        {"sub": "user-123", "email": 7},
        {"sub": "user-123", "name": []},
        {"sub": "user-123", "preferred_username": {}},
    ],
)
async def test_get_profile_rejects_invalid_profile_field_types(
    monkeypatch: pytest.MonkeyPatch, profile: dict[str, Any]
) -> None:
    install_transport(monkeypatch, lambda request: profile_response(profile))

    with pytest.raises(DomainError) as error:
        await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
            "synthetic-token", subject="user-123"
        )

    assert error.value.code == "identity_provider_unavailable"
    assert error.value.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize("profile", [None, [], "not-an-object", {}, {"sub": ""}, {"sub": 7}])
async def test_get_profile_rejects_nonobject_or_missing_subject(
    monkeypatch: pytest.MonkeyPatch, profile: object
) -> None:
    install_transport(monkeypatch, lambda request: profile_response(profile))

    with pytest.raises(DomainError) as error:
        await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
            "synthetic-token", subject="user-123"
        )

    assert error.value.code == "identity_provider_unavailable"
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_get_profile_rejects_mismatched_subject_without_exposing_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_transport(
        monkeypatch,
        lambda request: profile_response(
            {"sub": "different-user", "email": "private@example.test"}
        ),
    )

    with pytest.raises(DomainError) as error:
        await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
            "synthetic-secret-token", subject="user-123"
        )

    assert error.value.code == "unauthorized"
    assert error.value.status_code == 401
    assert "synthetic-secret-token" not in str(error.value)
    assert "private@example.test" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_get_profile_maps_provider_rejection_to_unauthorized(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(status_code, text="private provider body"),
    )

    with pytest.raises(DomainError) as error:
        await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
            "synthetic-secret-token", subject="user-123"
        )

    assert error.value.code == "unauthorized"
    assert error.value.status_code == 401
    assert "synthetic-secret-token" not in str(error.value)
    assert "private provider body" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [201, 202, 204, 206])
async def test_get_profile_rejects_non_200_success_status(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    profile = {"sub": "user-123", "email": "person@example.test"}

    def response(request: httpx.Request) -> httpx.Response:
        if status_code == 204:
            return httpx.Response(status_code)
        return httpx.Response(status_code, json=profile)

    install_transport(monkeypatch, response)

    with pytest.raises(DomainError) as error:
        await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
            "synthetic-token", subject="user-123"
        )

    assert error.value.code == "identity_provider_unavailable"
    assert error.value.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [302, 500])
async def test_get_profile_maps_redirects_and_server_errors_to_unavailable(
    monkeypatch: pytest.MonkeyPatch, status_code: int
) -> None:
    requests, options = install_transport(
        monkeypatch,
        lambda request: httpx.Response(
            status_code,
            headers={"Location": "https://other.example.test/collect"},
            text="private@example.test synthetic-secret-token",
        ),
    )

    with pytest.raises(DomainError) as error:
        await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
            "synthetic-secret-token", subject="user-123"
        )

    assert error.value.code == "identity_provider_unavailable"
    assert error.value.status_code == 503
    assert len(requests) == 1
    assert options[0]["follow_redirects"] is False
    assert all(request.url.host != "other.example.test" for request in requests)
    assert "synthetic-secret-token" not in str(error.value)
    assert "private@example.test" not in str(error.value)


@pytest.mark.asyncio
async def test_get_profile_maps_invalid_json_to_redacted_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200, text="private@example.test synthetic-secret-token"
        ),
    )

    with pytest.raises(DomainError) as error:
        await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
            "synthetic-secret-token", subject="user-123"
        )

    assert error.value.code == "identity_provider_unavailable"
    assert error.value.status_code == 503
    assert "synthetic-secret-token" not in str(error.value)
    assert "private@example.test" not in str(error.value)


@pytest.mark.asyncio
async def test_get_profile_maps_timeout_to_redacted_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic-secret-token")

    install_transport(monkeypatch, timeout)

    with pytest.raises(DomainError) as error:
        await UserInfoClient("https://issuer.example.test/userinfo").get_profile(
            "synthetic-secret-token", subject="user-123"
        )

    assert error.value.code == "identity_provider_unavailable"
    assert error.value.status_code == 503
    assert "synthetic-secret-token" not in str(error.value)
