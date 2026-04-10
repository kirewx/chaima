from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./chaima.db"
    secret_key: SecretStr = SecretStr("CHANGE-ME-IN-PRODUCTION")

    model_config = {"env_prefix": "CHAIMA_"}


settings = Settings()
