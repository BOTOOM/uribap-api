import pytest

from uribap_api.config import Settings


def test_identity_settings_parse_lists() -> None:
    settings = Settings(
        oidc_algorithms="RS256, ES256",
        oidc_required_scopes="openid profile",
    )
    assert settings.oidc_algorithms_list == ["RS256", "ES256"]
    assert settings.oidc_required_scopes_set == {"openid", "profile"}


def test_production_rejects_local_database() -> None:
    try:
        Settings(environment="production", database_url="postgresql+psycopg://u:p@localhost/db")
    except ValueError as error:
        assert "DATABASE_URL" in str(error)
    else:
        raise AssertionError("production localhost database must be rejected")


def userinfo_settings(**overrides: str) -> Settings:
    values = {
        "_env_file": None,
        "environment": "test",
        "oidc_issuer": "https://issuer.example.test",
        "oidc_userinfo_url": "https://issuer.example.test/oidc/v1/userinfo",
    }
    values.update(overrides)
    return Settings(**values)


def test_userinfo_accepts_same_origin_with_effective_default_ports() -> None:
    settings = userinfo_settings(
        oidc_issuer="https://issuer.example.test:443",
        oidc_userinfo_url="https://issuer.example.test/oidc/v1/userinfo",
    )
    assert settings.oidc_userinfo_url == "https://issuer.example.test/oidc/v1/userinfo"

    settings = userinfo_settings(
        oidc_issuer="http://issuer.example.test",
        oidc_userinfo_url="http://issuer.example.test:80/oidc/v1/userinfo",
    )
    assert settings.oidc_userinfo_url.endswith("/oidc/v1/userinfo")

    settings = userinfo_settings(
        oidc_issuer="https://issuer.example.test:8443",
        oidc_userinfo_url="https://issuer.example.test:8443/oidc/v1/userinfo",
    )
    assert settings.oidc_userinfo_url.endswith("/oidc/v1/userinfo")


@pytest.mark.parametrize(
    ("issuer", "userinfo"),
    [
        ("https://issuer.example.test", "https://other.example.test/userinfo"),
        ("https://issuer.example.test", "https://issuer.example.test:444/userinfo"),
        ("https://issuer.example.test", "https://issuer.example.test:0/userinfo"),
        ("https://issuer.example.test", "http://issuer.example.test/userinfo"),
        ("not-a-url", "https://issuer.example.test/userinfo"),
        ("https://issuer.example.test", "not-a-url"),
        ("https://user:pass@issuer.example.test", "https://issuer.example.test/userinfo"),
        ("https://issuer.example.test", "https://user:pass@issuer.example.test/userinfo"),
        ("https://issuer.example.test", "https://issuer.example.test/userinfo?token=x"),
        ("https://issuer.example.test", "https://issuer.example.test/userinfo#fragment"),
    ],
)
def test_userinfo_rejects_invalid_or_cross_origin_urls(issuer: str, userinfo: str) -> None:
    with pytest.raises(ValueError, match="OIDC_USERINFO_URL"):
        userinfo_settings(oidc_issuer=issuer, oidc_userinfo_url=userinfo)


def test_production_userinfo_requires_https() -> None:
    with pytest.raises(ValueError, match="must use HTTPS"):
        userinfo_settings(
            environment="production",
            database_url="postgresql+psycopg://u:p@db.example.test/uribap",
            oidc_issuer="http://issuer.example.test",
            oidc_userinfo_url="http://issuer.example.test/oidc/v1/userinfo",
        )
