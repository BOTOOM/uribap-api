import asyncio
import os
import time

import httpx
import jwt
import pytest

from uribap_api.config import get_settings
from uribap_api.infrastructure.identity.jwks_cache import JWKSCache


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("RUN_LOCAL_IDENTITY"),
    reason="Set RUN_LOCAL_IDENTITY=1 to run against disposable local ZITADEL",
)
def test_warm_jwks_cache_p95() -> None:
    settings = get_settings()
    with httpx.Client(timeout=5) as client:
        response = client.get(settings.oidc_jwks_url, headers={"Host": settings.oidc_jwks_host})
        response.raise_for_status()
        kid = response.json()["keys"][0]["kid"]
    token = jwt.encode(
        {"sub": "benchmark"},
        "benchmark-secret-0123456789012345",
        algorithm="HS256",
        headers={"kid": kid},
    )
    cache = JWKSCache(
        settings.oidc_jwks_url,
        host_header=settings.oidc_jwks_host,
        ttl_seconds=settings.oidc_jwks_ttl_seconds,
        timeout_seconds=settings.oidc_timeout_seconds,
    )
    samples: list[float] = []
    for _ in range(20):
        started = time.perf_counter()
        asyncio.run(cache.get_key(token))
        samples.append(time.perf_counter() - started)
    samples.sort()
    assert samples[int(len(samples) * 0.95)] < 0.5
