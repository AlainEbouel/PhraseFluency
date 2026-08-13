from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str
    session_secret: str
    frontend_url: str = "http://localhost:5173"
    additional_cors_origins: str = ""
    api_base_url: str = "http://localhost:8000"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 30.0
    tts_voice: str = "alloy"
    audio_storage_path: str = "/data/audio"

    session_cookie_name: str = "pf_session"
    session_ttl_days: int = 30

    admin_bootstrap_email: str | None = None
    admin_bootstrap_password: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        extra = [o.strip() for o in self.additional_cors_origins.split(",") if o.strip()]
        return [self.frontend_url, *extra]


@lru_cache
def get_settings() -> Settings:
    return Settings()
