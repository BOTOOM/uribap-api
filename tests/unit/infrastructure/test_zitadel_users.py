import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from starlette.requests import Request

from uribap_api.api.dependencies import get_user_directory
from uribap_api.config import Settings
from uribap_api.infrastructure.identity.zitadel_users import (
    ZitadelDirectoryError,
    ZitadelUserDirectory,
)

Handler = Callable[[httpx.Request], httpx.Response]


def settings_for_test(**overrides: str) -> Settings:
    values = {
        "_env_file": None,
        "environment": "test",
        "oidc_issuer": "https://issuer.example.test",
        "zitadel_service_token": "synthetic-service-token",
        "zitadel_organization_id": "org-123",
    }
    values.update(overrides)
    return Settings(**values)


def directory_for(
    handler: Handler,
) -> tuple[ZitadelUserDirectory, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def dispatch(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    settings = settings_for_test()
    client = httpx.Client(transport=httpx.MockTransport(dispatch))
    return ZitadelUserDirectory(settings, client=client), requests


def test_directory_dependency_uses_app_settings_only_when_enabled() -> None:
    application = FastAPI()
    request = Request({"type": "http", "app": application})
    application.state.settings = settings_for_test(
        zitadel_service_token="",
        zitadel_organization_id="",
    )

    assert get_user_directory(request) is None

    application.state.settings = settings_for_test()
    assert isinstance(get_user_directory(request), ZitadelUserDirectory)


def test_find_user_posts_exact_case_insensitive_query_with_bearer_auth() -> None:
    directory, requests = directory_for(
        lambda request: httpx.Response(200, json={"result": [{"userId": "user-123"}]})
    )

    result = directory.find_user_id_by_email("person@example.test")

    assert result == "user-123"
    assert len(requests) == 1
    assert requests[0].method == "POST"
    assert requests[0].url == "https://issuer.example.test/v2/users"
    assert requests[0].headers["Authorization"] == "Bearer synthetic-service-token"
    assert requests[0].extensions["timeout"]["connect"] == 5.0
    assert json.loads(requests[0].content) == {
        "query": {"limit": 1},
        "queries": [
            {"organizationIdQuery": {"organizationId": "org-123"}},
            {
                "emailQuery": {
                    "emailAddress": "person@example.test",
                    "method": "TEXT_QUERY_METHOD_EQUALS_IGNORE_CASE",
                }
            },
        ],
    }


@pytest.mark.parametrize("payload", [{}, {"result": []}])
def test_find_user_returns_none_for_missing_or_empty_result(payload: dict[str, Any]) -> None:
    directory, _ = directory_for(lambda request: httpx.Response(200, json=payload))

    assert directory.find_user_id_by_email("person@example.test") is None


def test_create_user_splits_and_truncates_display_name_and_includes_return_code() -> None:
    directory, requests = directory_for(
        lambda request: httpx.Response(200, json={"id": "user-123"})
    )
    display_name = "Ada Lovelace Byron" + "x" * 300

    result = directory.create_human_user("person@example.test", display_name)

    assert result == "user-123"
    assert requests[0].url == "https://issuer.example.test/v2/users/new"
    assert json.loads(requests[0].content) == {
        "organizationId": "org-123",
        "human": {
            "profile": {
                "givenName": "Ada",
                "familyName": ("Lovelace Byron" + "x" * 300)[:200],
                "displayName": display_name[:200],
            },
            "email": {"email": "person@example.test", "returnCode": {}},
        },
    }


def test_create_user_uses_email_local_part_without_display_name() -> None:
    directory, requests = directory_for(
        lambda request: httpx.Response(200, json={"id": "user-123"})
    )

    directory.create_human_user("given@example.test", None)

    profile = json.loads(requests[0].content)["human"]["profile"]
    assert profile == {"givenName": "given", "familyName": "given"}


def test_create_user_repeats_single_display_name_as_family_name() -> None:
    directory, requests = directory_for(
        lambda request: httpx.Response(200, json={"id": "user-123"})
    )

    directory.create_human_user("person@example.test", "  Ada  ")

    profile = json.loads(requests[0].content)["human"]["profile"]
    assert profile == {
        "givenName": "Ada",
        "familyName": "Ada",
        "displayName": "Ada",
    }


def test_send_invite_code_uses_default_login_v2_template() -> None:
    directory, requests = directory_for(lambda request: httpx.Response(200, json={}))

    directory.send_invite_code("user-123")

    assert requests[0].url == "https://issuer.example.test/v2/users/user-123/invite_code"
    assert requests[0].headers["Authorization"] == "Bearer synthetic-service-token"
    assert json.loads(requests[0].content) == {
        "sendCode": {
            "urlTemplate": (
                "https://issuer.example.test/ui/v2/login/verify?code={{.Code}}&userId={{.UserID}}"
                "&organization={{.OrgID}}&invite=true"
            ),
            "applicationName": "Uribap",
        }
    }


def test_non_success_response_does_not_expose_response_body_or_credentials() -> None:
    directory, _ = directory_for(
        lambda request: httpx.Response(
            503,
            text="synthetic-service-token person@example.test private response",
        )
    )

    with pytest.raises(ZitadelDirectoryError) as exc_info:
        directory.find_user_id_by_email("person@example.test")

    assert exc_info.value.status_code == 503
    assert "synthetic-service-token" not in str(exc_info.value)
    assert "person@example.test" not in str(exc_info.value)
    assert "private response" not in str(exc_info.value)


def test_transport_error_does_not_expose_credentials_or_email() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic-service-token person@example.test", request=request)

    directory, _ = directory_for(fail)

    with pytest.raises(ZitadelDirectoryError) as exc_info:
        directory.find_user_id_by_email("person@example.test")

    assert exc_info.value.status_code is None
    assert "synthetic-service-token" not in str(exc_info.value)
    assert "person@example.test" not in str(exc_info.value)
