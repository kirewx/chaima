import importlib

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


def test_session_ttl_setting_propagates_to_auth_module(monkeypatch):
    """The module-level constant in chaima.auth actually tracks the setting.

    ``test_cookie_and_jwt_lifetimes_agree`` reads ``settings.session_ttl_hours``
    on both the expected and actual side, so it would keep passing even if
    ``_SESSION_LIFETIME_SECONDS`` in chaima.auth were replaced with a
    hardcoded literal that happened to match the current default (e.g.
    ``2592000``) — a change that would silently disconnect the cookie/JWT
    lifetime from CHAIMA_SESSION_TTL_HOURS. This test closes that gap by
    reloading chaima.config and chaima.auth under a changed env var and
    checking the *reloaded* module's objects, not just the shared settings
    singleton.

    chaima.auth and chaima.config are reloaded (not just re-instantiated)
    because ``_SESSION_LIFETIME_SECONDS``, ``cookie_transport``, and
    ``settings`` are all computed once at import time. Other modules
    (chaima.app, chaima.dependencies, tests/test_api/conftest.py) import
    names out of chaima.auth at collection time, before this test runs, and
    keep their own bound references — reloading chaima.auth here does not
    retroactively change what they hold, so this cannot leak the patched
    48-hour setting into the app used by other tests. It could still leak
    into *other tests in this file*, which re-import from chaima.auth/
    chaima.config inside their own test bodies (i.e. dynamically, after this
    test may have run) — hence the explicit restore in `finally`.
    """
    import chaima.auth as auth_module
    import chaima.config as config_module

    monkeypatch.setenv("CHAIMA_SESSION_TTL_HOURS", "48")
    try:
        importlib.reload(config_module)
        importlib.reload(auth_module)

        assert auth_module.cookie_transport.cookie_max_age == 48 * 3600
        assert auth_module.get_jwt_strategy().lifetime_seconds == 48 * 3600
    finally:
        # Undo the env var *before* reloading back, so the reload picks up
        # the real default rather than the still-active override.
        monkeypatch.undo()
        importlib.reload(config_module)
        importlib.reload(auth_module)
