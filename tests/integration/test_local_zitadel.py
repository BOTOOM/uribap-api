import os

import httpx
import pytest

from uribap_api.config import get_settings


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get("RUN_LOCAL_IDENTITY"),
    reason="Set RUN_LOCAL_IDENTITY=1 to run against disposable local ZITADEL",
)
def test_local_zitadel_discovery_jwks_and_health() -> None:
    settings = get_settings()
    with httpx.Client(timeout=settings.oidc_timeout_seconds) as client:
        discovery = client.get(settings.oidc_issuer + "/.well-known/openid-configuration")
        jwks = client.get(settings.oidc_jwks_url, headers={"Host": settings.oidc_jwks_host})
        assert discovery.status_code == 200
        assert discovery.json()["issuer"] == settings.oidc_issuer
        assert jwks.status_code == 200
        assert len(jwks.json()["keys"]) > 0
