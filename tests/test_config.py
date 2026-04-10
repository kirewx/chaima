from chaima.config import AdminSettings


def test_admin_settings_defaults():
    s = AdminSettings()
    assert s.admin_email == "admin@chaima.dev"
    assert s.admin_password.get_secret_value() == "changeme"
    assert s.admin_group_name == "Admin"
    assert s.invite_ttl_hours == 48
