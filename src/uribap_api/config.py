from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Uribap API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://uribap:uribap@localhost:5432/uribap"
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=5, ge=0, le=20)
    database_pool_timeout_seconds: int = Field(default=5, ge=1, le=30)
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_jwks_host: str = ""
    oidc_algorithms: str = "RS256"
    oidc_required_scopes: str = ""
    oidc_jwks_ttl_seconds: int = Field(default=300, ge=10, le=3600)
    oidc_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    oidc_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    smtp_host: str = "localhost"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "uribap@localhost"
    smtp_use_tls: bool = False
    smtp_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    web_base_url: str = "http://localhost:3000"

    @model_validator(mode="after")
    def validate_production_configuration(self) -> Settings:
        if self.environment == "production" and "localhost" in str(self.database_url):
            raise ValueError("DATABASE_URL must not point to localhost in production")
        return self

    @property
    def allowed_cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def oidc_algorithms_list(self) -> list[str]:
        return [
            algorithm.strip() for algorithm in self.oidc_algorithms.split(",") if algorithm.strip()
        ]

    @property
    def oidc_required_scopes_set(self) -> set[str]:
        return {scope.strip() for scope in self.oidc_required_scopes.split() if scope.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
