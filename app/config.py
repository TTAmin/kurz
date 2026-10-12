from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from KURZ_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="KURZ_")

    database_url: str = "sqlite:///./kurz.db"
    base_url: str = "http://localhost:8000"
    code_length: int = 7
    log_level: str = "INFO"
    db_connect_timeout_seconds: float = 60.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
