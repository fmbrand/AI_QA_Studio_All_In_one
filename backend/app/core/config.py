"""Application settings, loaded from environment variables (and a .env file in development)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRETS = {"", "change-me", "changeme", "secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://postgres@127.0.0.1:5434/ai_qa_studio"

    # Auth
    jwt_secret: str = Field(default="", min_length=0)
    access_token_minutes: int = 15
    refresh_token_days: int = 14
    cookie_secure: bool = False
    max_failed_logins: int = 10
    lockout_minutes: int = 15
    login_rate_limit_per_minute: int = 5

    # HTTP
    cors_origins: list[str] = ["http://localhost:3000"]

    # Storage
    storage_driver: Literal["local"] = "local"
    storage_local_dir: Path = Path("./storage")
    max_upload_mb: int = 25
    signed_url_seconds: int = 300

    # Worker
    worker_poll_seconds: float = 1.0
    job_stale_minutes: int = 10
    job_max_attempts: int = 3

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    def check_secrets(self) -> None:
        if self.environment == "production" and (self.jwt_secret in _WEAK_SECRETS or len(self.jwt_secret) < 32):
            raise RuntimeError("JWT_SECRET must be set to a random string of at least 32 characters")

    @property
    def effective_jwt_secret(self) -> str:
        if self.jwt_secret:
            return self.jwt_secret
        if self.environment == "production":
            raise RuntimeError("JWT_SECRET is required in production")
        return "dev-only-insecure-secret-do-not-use-in-production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.check_secrets()
    return settings
