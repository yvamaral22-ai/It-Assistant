from functools import lru_cache
from pathlib import Path
import secrets

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
    maintenance_mode: bool = False
    log_level: str = "INFO"
    log_dir: str = "data/logs"
    backup_retention_days: int = 30
    allowed_hosts: str = "localhost,127.0.0.1,XC01L0093,XC01L0093.xcmg-america.local,10.128.72.95"
    public_base_url: str = ""
    session_max_age_seconds: int = 7_200
    max_request_body_bytes: int = 1_048_576
    api_docs_enabled: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_session_secret(settings: Settings) -> str:
    """Use the configured secret or persist a local-only generated secret."""
    if settings.secret_key != "change-this-value":
        return settings.secret_key
    if settings.is_production:
        raise RuntimeError("Defina uma SECRET_KEY forte antes de iniciar em produção.")
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(exist_ok=True)
    secret_file = data_dir / ".session_secret"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()
    value = secrets.token_urlsafe(48)
    secret_file.write_text(value, encoding="utf-8")
    return value
