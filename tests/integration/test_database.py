import pytest
from sqlalchemy import Engine, text


@pytest.mark.integration
def test_database_connection(integration_engine: Engine) -> None:
    with integration_engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
