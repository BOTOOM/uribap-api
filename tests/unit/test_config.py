import pytest
from pydantic import ValidationError

from uribap_api.config import Settings


def test_development_settings_use_safe_local_defaults() -> None:
    settings = Settings()

    assert settings.environment == "development"
    assert settings.database_pool_size == 5
    assert settings.allowed_cors_origins == ["http://localhost:3000"]


def test_production_rejects_local_database() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", database_url="postgresql+psycopg://user:pass@localhost/db")
