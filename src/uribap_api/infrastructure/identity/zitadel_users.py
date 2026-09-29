from urllib.parse import quote

import httpx

from uribap_api.config import Settings


class ZitadelDirectoryError(Exception):
    def __init__(self, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__("ZITADEL directory request failed")


class ZitadelUserDirectory:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self._settings = settings
        self._client = client

    def find_user_id_by_email(self, email: str) -> str | None:
        response = self._post(
            "/v2/users",
            {
                "query": {"limit": 1},
                "queries": [
                    {
                        "emailQuery": {
                            "emailAddress": email,
                            "method": "TEXT_QUERY_METHOD_EQUALS_IGNORE_CASE",
                        }
                    }
                ],
            },
        )
        payload = self._json(response)
        result = payload.get("result")
        if result is None or result == []:
            return None
        if not isinstance(result, list) or not isinstance(result[0], dict):
            raise ZitadelDirectoryError(status_code=response.status_code)
        user_id = result[0].get("userId")
        if not isinstance(user_id, str) or not user_id:
            raise ZitadelDirectoryError(status_code=response.status_code)
        return user_id

    def create_human_user(self, email: str, display_name: str | None) -> str:
        given_name, family_name, normalized_display_name = self._profile_names(
            email, display_name
        )
        profile = {"givenName": given_name, "familyName": family_name}
        if normalized_display_name is not None:
            profile["displayName"] = normalized_display_name
        response = self._post(
            "/v2/users/new",
            {
                "organizationId": self._settings.zitadel_organization_id,
                "human": {
                    "profile": profile,
                    "email": {"email": email, "returnCode": {}},
                },
            },
        )
        payload = self._json(response)
        user_id = payload.get("id")
        if not isinstance(user_id, str) or not user_id:
            raise ZitadelDirectoryError(status_code=response.status_code)
        return user_id

    def send_invite_code(self, user_id: str) -> None:
        self._post(
            f"/v2/users/{quote(user_id, safe='')}/invite_code",
            {
                "sendCode": {
                    "urlTemplate": self._settings.zitadel_invite_url_template,
                    "applicationName": self._settings.zitadel_invite_application_name,
                }
            },
        )

    def _post(self, path: str, body: dict[str, object]) -> httpx.Response:
        url = f"{self._settings.zitadel_api_url}{path}"
        headers = {
            "Authorization": f"Bearer {self._settings.zitadel_service_token}",
            "Accept": "application/json",
        }
        try:
            timeout = self._settings.oidc_timeout_seconds
            if self._client is None:
                with httpx.Client(
                    timeout=timeout,
                    follow_redirects=False,
                ) as client:
                    response = client.post(
                        url,
                        headers=headers,
                        json=body,
                        timeout=timeout,
                        follow_redirects=False,
                    )
            else:
                response = self._client.post(
                    url,
                    headers=headers,
                    json=body,
                    timeout=timeout,
                    follow_redirects=False,
                )
        except httpx.HTTPError:
            raise ZitadelDirectoryError() from None
        if not 200 <= response.status_code < 300:
            raise ZitadelDirectoryError(status_code=response.status_code)
        return response

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, object]:
        try:
            payload = response.json()
        except ValueError:
            raise ZitadelDirectoryError(status_code=response.status_code) from None
        if not isinstance(payload, dict):
            raise ZitadelDirectoryError(status_code=response.status_code)
        return payload

    @staticmethod
    def _profile_names(
        email: str, display_name: str | None
    ) -> tuple[str, str, str | None]:
        if display_name is None or not display_name.strip():
            local_part = email.partition("@")[0]
            return local_part[:200], local_part[:200], None
        normalized = " ".join(display_name.split())
        given_name, separator, remaining_name = normalized.partition(" ")
        family_name = remaining_name if separator else given_name
        return given_name[:200], family_name[:200], normalized[:200]
