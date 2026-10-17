from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "production"] = "development"
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    database_url: str
    cors_origins: str = "http://localhost:3000"
    sla_at_risk_threshold: float = 0.75
    reopen_window_days: int = 7
    internal_task_token: str = "local-internal-token"
    log_level: str = "INFO"
    app_version: str = "1.0.0"

    @field_validator("app_env", mode="before")
    @classmethod
    def _default_app_env(cls, value: object) -> object:
        return value if value else "development"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _fail_fast_in_production(self) -> "Settings":
        if self.app_env == "production" and len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
