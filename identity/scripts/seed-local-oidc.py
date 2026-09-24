from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NoReturn

import httpx

IDENTITY_DIR = Path(__file__).resolve().parents[1]
OUTPUT_FILE = Path(os.environ.get("SEED_OUTPUT_FILE", str(IDENTITY_DIR / ".env.oidc.local")))
ISSUER = os.environ.get("OIDC_ISSUER", "http://localhost:8080").rstrip("/")
ADMIN_TOKEN = os.environ.get("ZITADEL_ADMIN_TOKEN", "")
PROJECT_NAME = os.environ.get("ZITADEL_LOCAL_PROJECT_NAME", "Uribap Local")
WEB_CLIENT_NAME = os.environ.get("ZITADEL_LOCAL_WEB_CLIENT_NAME", "Uribap Web Local")
WEB_BASE_URL = os.environ.get("WEB_BASE_URL", "http://localhost:3000").rstrip("/")
DEV_MODE = WEB_BASE_URL.startswith("http://localhost") or WEB_BASE_URL.startswith(
    "http://127.0.0.1"
)


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def request(client: httpx.Client, method: str, path: str, **kwargs: object) -> dict[str, object]:
    response = client.request(method, f"{ISSUER}{path}", **kwargs)
    if response.is_error:
        if response.status_code == 403:
            fail(
                "ZITADEL Admin API rejected the local token; use a disposable token "
                "with project/app permissions."
            )
        fail(f"ZITADEL request failed ({response.status_code}) at {path}")
    return response.json()


def main() -> int:
    with httpx.Client(timeout=10.0) as client:
        discovery = request(client, "GET", "/.well-known/openid-configuration")
        jwks = request(client, "GET", "/oauth/v2/keys")
        print(f"issuer={discovery.get('issuer')}")
        print(f"jwks_keys={len(jwks.get('keys', [])) if isinstance(jwks.get('keys'), list) else 0}")

        if not ADMIN_TOKEN:
            print("ZITADEL is ready. Set ZITADEL_ADMIN_TOKEN for project/application seed.")
            return 0

        headers = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}
        existing: dict[str, str] = {}
        if OUTPUT_FILE.exists():
            for line in OUTPUT_FILE.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    existing[key] = value

        project_id = existing.get("ZITADEL_PROJECT_ID", "")
        client_id = existing.get("AUTH_ZITADEL_ID", "")
        client_secret = existing.get("AUTH_ZITADEL_SECRET", "")
        if not project_id:
            project = request(
                client,
                "POST",
                "/management/v1/projects",
                headers=headers,
                json={"name": PROJECT_NAME},
            )
            project_id = str(project.get("id", ""))
            if not project_id:
                fail("ZITADEL did not return a project ID")

        if not client_id or not client_secret:
            application = request(
                client,
                "POST",
                f"/management/v1/projects/{project_id}/apps/oidc",
                headers=headers,
                json={
                    "name": WEB_CLIENT_NAME,
                    "redirectUris": [
                        f"{WEB_BASE_URL}/api/auth/callback/zitadel",
                        *(
                            ["http://127.0.0.1:3000/api/auth/callback/zitadel"]
                            if DEV_MODE
                            else []
                        ),
                    ],
                    "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
                    "grantTypes": [
                        "OIDC_GRANT_TYPE_AUTHORIZATION_CODE",
                        "OIDC_GRANT_TYPE_REFRESH_TOKEN",
                    ],
                    "appType": "OIDC_APP_TYPE_WEB",
                    "authMethodType": "OIDC_AUTH_METHOD_TYPE_BASIC",
                    "postLogoutRedirectUris": [
                        f"{WEB_BASE_URL}/",
                        *(["http://127.0.0.1:3000/"] if DEV_MODE else []),
                    ],
                    "version": "OIDC_VERSION_1_0",
                    "devMode": DEV_MODE,
                    "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
                    "idTokenUserinfoAssertion": True,
                    "skipNativeAppSuccessPage": True,
                },
            )
            client_id = str(application.get("clientId", ""))
            client_secret = str(application.get("clientSecret", ""))
            if not client_id or not client_secret:
                fail("ZITADEL did not return local OIDC client credentials")

        OUTPUT_FILE.touch(mode=0o600, exist_ok=True)
        OUTPUT_FILE.chmod(0o600)
        OUTPUT_FILE.write_text(
            "\n".join(
                [
                    "# Generated locally; ignored and never commit this file.",
                    f"ZITADEL_PROJECT_ID={project_id}",
                    f"AUTH_ZITADEL_ID={client_id}",
                    f"AUTH_ZITADEL_SECRET={client_secret}",
                    f"AUTH_ZITADEL_ISSUER={ISSUER}",
                    f"OIDC_ISSUER={ISSUER}",
                    f"OIDC_JWKS_URL={ISSUER}/oauth/v2/keys",
                    f"OIDC_USERINFO_URL={ISSUER}/oidc/v1/userinfo",
                    f"OIDC_AUDIENCE={project_id}",
                    "OIDC_REQUIRED_SCOPES=openid",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        print(f"project_id={project_id}")
        print(f"client_id={client_id}")
        print(f"generated_env={OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
