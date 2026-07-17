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
