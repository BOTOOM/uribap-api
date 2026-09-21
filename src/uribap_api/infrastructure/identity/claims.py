from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from uribap_api.domain.shared.errors import DomainError


@dataclass(frozen=True, slots=True)
class IdentityClaims:
    issuer: str
    subject: str
    email: str | None
    email_verified: bool
    display_name: str | None
    scopes: frozenset[str]
    raw: dict[str, Any]


def parse_identity_claims(payload: dict[str, Any], *, expected_issuer: str) -> IdentityClaims:
    issuer = payload.get("iss")
    subject = payload.get("sub")
    if not isinstance(issuer, str) or issuer != expected_issuer:
        raise DomainError(
            "unauthorized", "Authentication failed", "The token issuer is invalid.", 401
        )
    if not isinstance(subject, str) or not subject:
        raise DomainError(
            "unauthorized", "Authentication failed", "The token subject is missing.", 401
        )
    expiration = payload.get("exp")
    if not isinstance(expiration, (int, float)) or expiration <= datetime.now(UTC).timestamp():
        raise DomainError("unauthorized", "Authentication failed", "The token is expired.", 401)
    scope_claim = payload.get("scope", "")
    scopes = frozenset(scope_claim.split()) if isinstance(scope_claim, str) else frozenset()
    return IdentityClaims(
        issuer=issuer,
        subject=subject,
        email=payload.get("email") if isinstance(payload.get("email"), str) else None,
        email_verified=payload.get("email_verified") is True,
        display_name=(payload.get("name") or payload.get("preferred_username"))
        if isinstance(payload.get("name") or payload.get("preferred_username"), str)
        else None,
        scopes=scopes,
        raw=payload,
    )


def require_scopes(claims: IdentityClaims, required: set[str]) -> None:
    missing = required.difference(claims.scopes)
    if missing:
        raise DomainError(
            "forbidden",
            "Permission denied",
            "The token does not contain the required scope.",
            403,
        )
