from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Shipped defaults, exported so startup checks can detect when they are
# still in use (see ``chaima.app``). Never deploy with these values.
DEFAULT_SECRET_KEY = "CHANGE-ME-IN-PRODUCTION"
DEFAULT_ADMIN_PASSWORD = "changeme"


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./chaima.db"
    secret_key: SecretStr = SecretStr(DEFAULT_SECRET_KEY)
    # Marks auth cookies as `Secure` (HTTPS-only). Defaults to True for
    # production safety; set CHAIMA_COOKIE_SECURE=false when testing over
    # plain HTTP on a LAN, otherwise browsers reject the cookie and login
    # appears to succeed but `/users/me` returns 401.
    cookie_secure: bool = True
    # Base URL used to build invite links (e.g. https://chaima.example.com).
    # When None, the frontend falls back to `window.location.origin`, which
    # leaks `localhost` if an admin generates the link from the dev machine.
    public_base_url: str | None = None
    # When True, refuse to start while shipped default secrets are still in
    # use (secret_key / admin password). Keeps local dev frictionless while
    # letting container deploys hard-fail via CHAIMA_REQUIRE_SECURE_CONFIG=true.
    require_secure_config: bool = False
    # GESTIS (DGUV hazardous-substance database) API. The shipped key is the
    # public web-client key from GESTIS's own SPA (env-config.js) — it is
    # served in cleartext to every browser, so it is public by design, not a
    # secret. Override via CHAIMA_GESTIS_API_KEY like any other setting.
    gestis_api_base: str = "https://gestis-api.dguv.de/api"
    gestis_api_key: str = "dddiiasjhduuvnnasdkkwUUSHhjaPPKMasd"

    model_config = SettingsConfigDict(env_prefix="CHAIMA_")


settings = Settings()


class AdminSettings(BaseSettings):
    """Configuration for the initial superuser seed account.

    Attributes
    ----------
    admin_email : str
        Email address for the seed superuser.
    admin_password : SecretStr
        Password for the seed superuser.
    admin_group_name : str
        Name of the seed group.
    invite_ttl_hours : int
        Default time-to-live for invite links in hours.
    """

    admin_email: str = "admin@chaima.dev"
    admin_password: SecretStr = SecretStr(DEFAULT_ADMIN_PASSWORD)
    admin_group_name: str = "Admin"
    invite_ttl_hours: int = 48

    model_config = SettingsConfigDict(env_prefix="CHAIMA_")


admin_settings = AdminSettings()
