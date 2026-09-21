import pytest


@pytest.mark.integration
@pytest.mark.skip(
    reason="Requires the disposable local ZITADEL stack and a configured JWKS endpoint"
)
def test_warm_jwks_cache_p95() -> None:
    pytest.fail("Run the local identity benchmark after configuring ZITADEL JWKS")
