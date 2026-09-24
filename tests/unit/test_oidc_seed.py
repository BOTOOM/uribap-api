import contextlib
import importlib.util
import io
from pathlib import Path
from typing import Any

import httpx
import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "identity/scripts/seed-local-oidc.py"


def load_seed_script() -> Any:
    spec = importlib.util.spec_from_file_location("seed_local_oidc", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def install_seed_transport(
    monkeypatch: pytest.MonkeyPatch, handler: Any
) -> list[httpx.Request]:
    requests: list[httpx.Request] = []
    original_client = httpx.Client

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    def create_client(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handle)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", create_client)
    return requests


def test_seed_creates_jwt_profile_client_with_private_output_and_reuses_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seed = load_seed_script()
    output_file = tmp_path / "seed.env"
    seed.OUTPUT_FILE = output_file
    seed.ISSUER = "https://issuer.example.test"
    seed.ADMIN_TOKEN = "synthetic-admin-token"
    seed.PROJECT_NAME = "Uribap Synthetic"
    seed.WEB_CLIENT_NAME = "Uribap Web Synthetic"
    seed.WEB_BASE_URL = "https://web.example.test"
    seed.DEV_MODE = False
    application_payloads: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/.well-known/openid-configuration":
            return httpx.Response(200, json={"issuer": seed.ISSUER})
        if request.url.path == "/oauth/v2/keys":
            return httpx.Response(200, json={"keys": [{"kid": "synthetic"}]})
        if request.url.path == "/management/v1/projects":
            return httpx.Response(200, json={"id": "synthetic-project-id"})
        if request.url.path == "/management/v1/projects/synthetic-project-id/apps/oidc":
            application_payloads.append(request.read().decode())
            return httpx.Response(
                200,
                json={
                    "clientId": "synthetic-client-id",
                    "clientSecret": "synthetic-client-secret",
                },
            )
        raise AssertionError(f"Unexpected synthetic request: {request.method} {request.url.path}")

    requests = install_seed_transport(monkeypatch, respond)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        assert seed.main() == 0

    assert len(application_payloads) == 1
    app = httpx.Response(200, text=application_payloads[0]).json()
    assert app["accessTokenType"] == "OIDC_TOKEN_TYPE_JWT"
    assert app["authMethodType"] == "OIDC_AUTH_METHOD_TYPE_BASIC"
    assert "OIDC_GRANT_TYPE_AUTHORIZATION_CODE" in app["grantTypes"]
    assert "OIDC_GRANT_TYPE_REFRESH_TOKEN" in app["grantTypes"]
    assert app["idTokenUserinfoAssertion"] is True
    assert "https://web.example.test/api/auth/callback/zitadel" in app["redirectUris"]
    assert "https://web.example.test/" in app["postLogoutRedirectUris"]
    contents = output_file.read_text(encoding="utf-8")
    assert "OIDC_USERINFO_URL=https://issuer.example.test/oidc/v1/userinfo" in contents
    assert "OIDC_AUDIENCE=synthetic-project-id" in contents
    assert "OIDC_REQUIRED_SCOPES=\n" in contents
    assert "synthetic-client-secret" not in stdout.getvalue()
    assert "synthetic-admin-token" not in stdout.getvalue()
    assert output_file.stat().st_mode & 0o777 == 0o600

    initial_post_count = sum(request.method == "POST" for request in requests)
    with contextlib.redirect_stdout(io.StringIO()):
        assert seed.main() == 0
    assert sum(request.method == "POST" for request in requests) == initial_post_count
