from chaima.config import AdminSettings


def test_admin_settings_defaults():
    s = AdminSettings()
    assert s.admin_email == "admin@chaima.dev"
    assert s.admin_password.get_secret_value() == "changeme"
    assert s.admin_group_name == "Admin"
    assert s.invite_ttl_hours == 48


def test_gestis_settings_defaults():
    from chaima.config import Settings

    s = Settings()
    assert s.gestis_api_base == "https://gestis-api.dguv.de/api"
    # Shipped default is GESTIS's public web-client key (served in cleartext
    # by their own SPA) — non-empty, overridable via env.
    assert s.gestis_api_key


def test_gestis_settings_env_override(monkeypatch):
    from chaima.config import Settings

    monkeypatch.setenv("CHAIMA_GESTIS_API_BASE", "https://example.invalid/api")
    monkeypatch.setenv("CHAIMA_GESTIS_API_KEY", "test-key")
    s = Settings()
    assert s.gestis_api_base == "https://example.invalid/api"
    assert s.gestis_api_key == "test-key"


def test_session_ttl_default_is_30_days():
    from chaima.config import Settings

    s = Settings()
    assert s.session_ttl_hours == 720


def test_session_ttl_env_override(monkeypatch):
    from chaima.config import Settings

    monkeypatch.setenv("CHAIMA_SESSION_TTL_HOURS", "48")
    s = Settings()
    assert s.session_ttl_hours == 48


def test_cookie_and_jwt_lifetimes_agree():
    """The cookie's max-age and the JWT's expiry must never drift apart.

    A cookie that outlives its token logs the user out with a 401 on a
    request the browser still considers authenticated; a token that
    outlives its cookie wastes the remaining validity. Both come from
    ``session_ttl_hours``.
    """
    from chaima.auth import cookie_transport, get_jwt_strategy
    from chaima.config import settings

    expected = settings.session_ttl_hours * 3600
    assert cookie_transport.cookie_max_age == expected
    assert get_jwt_strategy().lifetime_seconds == expected
