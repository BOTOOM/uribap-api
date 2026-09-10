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
