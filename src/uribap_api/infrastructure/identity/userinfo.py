from typing import Any

import httpx

from uribap_api.domain.identity.policies import normalize_email
from uribap_api.domain.shared.errors import DomainError


class UserInfoClient:
    def __init__(
        self, url: str, *, timeout_seconds: float = 5.0, connect_host: str = ""
    ) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.connect_host = connect_host

    async def get_profile(self, token: str, *, subject: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds, follow_redirects=False
            ) as client:
                request_url = httpx.URL(self.url)
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
                if self.connect_host:
                    headers["Host"] = request_url.netloc.decode("ascii")
                    request_url = request_url.copy_with(host=self.connect_host)
                response = await client.get(request_url, headers=headers)
                if response.status_code in {401, 403}:
                    raise DomainError(
                        "unauthorized",
                        "Authentication failed",
                        "The identity provider rejected the access token.",
                        401,
                    )
                response.raise_for_status()
                profile = response.json()
        except (httpx.HTTPError, ValueError):
            raise DomainError(
                "identity_provider_unavailable",
                "Identity provider unavailable",
                "The identity provider profile could not be retrieved.",
                503,
            ) from None
        if not isinstance(profile, dict) or not isinstance(profile.get("sub"), str) or not profile[
            "sub"
        ]:
            raise DomainError(
                "identity_provider_unavailable",
                "Identity provider unavailable",
                "The identity provider returned an invalid profile.",
                503,
            )
        if profile["sub"] != subject:
            raise DomainError(
                "unauthorized",
                "Authentication failed",
                "The identity provider profile does not match the access token.",
                401,
            )
        if any(
            profile.get(field) is not None and not isinstance(profile[field], str)
            for field in ("email", "name", "preferred_username")
        ) or ("email_verified" in profile and not isinstance(profile["email_verified"], bool)):
            raise DomainError(
                "identity_provider_unavailable",
                "Identity provider unavailable",
                "The identity provider returned an invalid profile.",
                503,
            )
        email = profile.get("email")
        if isinstance(email, str):
            try:
                email = normalize_email(email)
            except ValueError:
                raise DomainError(
                    "identity_provider_unavailable",
                    "Identity provider unavailable",
                    "The identity provider returned an invalid profile.",
                    503,
                ) from None
        else:
            email = None
        return {
            "email": email,
            "email_verified": bool(email) and profile.get("email_verified") is True,
            "name": profile.get("name"),
            "preferred_username": profile.get("preferred_username"),
        }
