import os
from urllib.request import urlopen

import pytest


@pytest.mark.integration
def test_compose_api_health() -> None:
    if os.getenv("RUN_COMPOSE_SMOKE") != "1":
        pytest.skip("Set RUN_COMPOSE_SMOKE=1 after starting the API container")

    with urlopen("http://localhost:8010/api/v1/health/live", timeout=2) as response:
        assert response.status == 200
