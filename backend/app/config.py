from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str #if it's missing, appr aises an error
    app_env: str = "local"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings: #cached so the .env file is only read once, not on every start
    return Settings()
