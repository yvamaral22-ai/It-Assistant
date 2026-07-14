from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Environment-driven application settings."""

    app_name: str = "IT Self-Service Assistant"
    app_env: str = "development"
    app_debug: bool = False
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'it_assistant.db').as_posix()}"
    secret_key: str = "change-this-value"
    glpi_enabled: bool = False
    ad_enabled: bool = False
    microsoft_graph_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

