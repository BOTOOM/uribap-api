import asyncio
import time
from typing import Any

import httpx
import jwt

from uribap_api.domain.shared.errors import DomainError


class JWKSCache:
    def __init__(
        self,
        url: str,
        *,
        host_header: str = "",
        ttl_seconds: int = 300,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.url = url
        self.host_header = host_header
        self.ttl_seconds = ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._lock = asyncio.Lock()

    async def get_key(self, token: str) -> Any:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise DomainError(
                "unauthorized", "Authentication failed", "The token is malformed.", 401
            ) from exc
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise DomainError(
                "unauthorized", "Authentication failed", "The token key id is missing.", 401
            )
        if time.monotonic() < self._expires_at and kid in self._keys:
            return self._keys[kid]
        await self._refresh()
        if kid not in self._keys:
            await self._refresh(force=True)
        try:
            return self._keys[kid]
        except KeyError as exc:
            raise DomainError(
                "unauthorized", "Authentication failed", "The signing key is unknown.", 401
            ) from exc

    async def _refresh(self, *, force: bool = False) -> None:
        async with self._lock:
            if not force and time.monotonic() < self._expires_at and self._keys:
                return
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    headers = {"Host": self.host_header} if self.host_header else None
                    response = await client.get(self.url, headers=headers)
                    response.raise_for_status()
                    payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise DomainError(
                    "identity_provider_unavailable",
                    "Identity provider unavailable",
                    "The identity provider signing keys could not be retrieved.",
                    503,
                ) from exc
            keys = payload.get("keys") if isinstance(payload, dict) else None
            if not isinstance(keys, list):
                raise DomainError(
                    "identity_provider_unavailable",
                    "Identity provider unavailable",
                    "The identity provider returned an invalid signing-key document.",
                    503,
                )
            self._keys = {
                key["kid"]: jwt.PyJWK.from_dict(key).key
                for key in keys
                if isinstance(key, dict) and isinstance(key.get("kid"), str)
            }
            self._expires_at = time.monotonic() + self.ttl_seconds

    async def ready(self) -> bool:
        await self._refresh()
        return bool(self._keys)
