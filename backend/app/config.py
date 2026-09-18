from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./cvinsight.db"
    lookup_url: str | None = None
    cors_origins: str = "http://localhost:5173"
    frontend_dist: str = "../frontend/dist"

    model_config = SettingsConfigDict(env_prefix="CVINSIGHT_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
