from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./chaima.db"
    secret_key: SecretStr = SecretStr("CHANGE-ME-IN-PRODUCTION")

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

    admin_email: str = "admin@chaima.local"
    admin_password: SecretStr = SecretStr("changeme")
    admin_group_name: str = "Admin"
    invite_ttl_hours: int = 48

    model_config = SettingsConfigDict(env_prefix="CHAIMA_")


admin_settings = AdminSettings()
