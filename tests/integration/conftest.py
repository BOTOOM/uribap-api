from collections.abc import Generator

import pytest
from sqlalchemy import Engine

from uribap_api.config import get_settings
from uribap_api.infrastructure.database import create_database_engine


@pytest.fixture(scope="session")
def integration_engine() -> Generator[Engine]:
    engine = create_database_engine(get_settings())
    try:
        yield engine
    finally:
        engine.dispose()
