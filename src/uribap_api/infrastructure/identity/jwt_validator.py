from dataclasses import replace
from typing import Any

import jwt

from uribap_api.config import Settings
from uribap_api.domain.shared.errors import DomainError
from uribap_api.infrastructure.identity.claims import (
    IdentityClaims,
    parse_identity_claims,
    require_scopes,
)
from uribap_api.infrastructure.identity.jwks_cache import JWKSCache
from uribap_api.infrastructure.identity.userinfo import UserInfoClient


def _display_name(payload: dict[str, Any], profile: dict[str, Any]) -> str | None:
    for source in (
        profile.get("name"),
        profile.get("preferred_username"),
        payload.get("name"),
        payload.get("preferred_username"),
    ):
        if isinstance(source, str) and source:
            return source
    return None


class TokenValidator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache = JWKSCache(
            settings.oidc_jwks_url,
            host_header=settings.oidc_jwks_host,
            ttl_seconds=settings.oidc_jwks_ttl_seconds,
            timeout_seconds=settings.oidc_timeout_seconds,
        )
        self.userinfo = (
            UserInfoClient(
                settings.oidc_userinfo_url,
                timeout_seconds=settings.oidc_timeout_seconds,
                connect_host=settings.oidc_userinfo_connect_host,
            )
            if settings.oidc_userinfo_url
            else None
        )

    async def validate(self, token: str) -> IdentityClaims:
        if (
            not self.settings.oidc_issuer
            or not self.settings.oidc_audience
            or not self.settings.oidc_jwks_url
        ):
            raise DomainError(
                "identity_provider_unavailable",
                "Identity provider unavailable",
                "OIDC validation is not configured.",
                503,
            )
        key = await self.cache.get_key(token)
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=self.settings.oidc_algorithms_list,
                audience=self.settings.oidc_audience,
                issuer=self.settings.oidc_issuer,
                options={"require": ["iss", "sub", "aud", "exp"]},
                leeway=self.settings.oidc_clock_skew_seconds,
            )
        except jwt.PyJWTError as exc:
            raise DomainError(
                "unauthorized", "Authentication failed", "The access token is invalid.", 401
            ) from exc
        claims = parse_identity_claims(payload, expected_issuer=self.settings.oidc_issuer)
        require_scopes(claims, self.settings.oidc_required_scopes_set)
        if self.userinfo is not None:
            profile = await self.userinfo.get_profile(token, subject=claims.subject)
            enriched_payload = {
                **payload,
                "email": profile["email"],
                "email_verified": profile["email_verified"],
            }
            for field in ("name", "preferred_username"):
                if profile[field] is not None:
                    enriched_payload[field] = profile[field]
            claims = replace(
                claims,
                email=profile["email"],
                email_verified=profile["email_verified"],
                display_name=_display_name(payload, profile),
                raw=enriched_payload,
            )
        return claims

    async def ready(self) -> bool:
        if not self.settings.oidc_jwks_url:
            return False
        return await self.cache.ready()
