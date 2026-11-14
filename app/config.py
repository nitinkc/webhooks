"""Runtime configuration, loaded from environment variables and .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Shared secret used to sign and verify webhook payloads — the same role
    # GitHub's "webhook secret" plays. Anyone holding it can forge events.
    webhook_secret: str = "dev-secret-change-me"

    # Provider-side delivery behavior.
    max_attempts: int = 4            # total HTTP tries per delivery
    retry_delay_seconds: float = 0.5  # first retry delay; doubles each retry


@lru_cache
def get_settings() -> Settings:
    return Settings()
