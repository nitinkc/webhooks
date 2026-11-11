"""Runtime configuration, loaded from environment variables and .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_AUTH_TOKEN = "local-dev-token"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Twilio credentials — leave SID empty until you have a real account.
    twilio_account_sid: str = ""
    twilio_auth_token: str = DEV_AUTH_TOKEN
    twilio_phone_number: str = "+15555550100"

    # mock_mode=True: outbound SMS is logged instead of sent via Twilio.
    mock_mode: bool = True

    # The URL Twilio "called" — signature validation is computed against this.
    # With a tunnel this becomes the public URL, e.g. https://xyz.ngrok-free.app
    app_base_url: str = "http://localhost:8000"

    @property
    def has_real_credentials(self) -> bool:
        return bool(self.twilio_account_sid) and self.twilio_auth_token != DEV_AUTH_TOKEN

    @property
    def validate_signatures(self) -> bool:
        return bool(self.twilio_auth_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
