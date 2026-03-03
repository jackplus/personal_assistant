from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    app_name: str = "Personal Assistant MVP"
    env: str = "dev"
    database_url: str = f"sqlite:///{(DATA_DIR / 'assistant.db').as_posix()}"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"

    telegram_bot_token: str | None = None
    telegram_notify_chat_id: str | None = None
    telegram_sync_mode: str = "bot"
    telegram_user_api_id: int | None = None
    telegram_user_api_hash: str | None = None
    telegram_user_string_session: str | None = None
    telegram_user_dialog_limit: int = 30
    telegram_user_message_limit: int = 100
    telegram_user_include_outgoing: bool = False

    google_calendar_mock_path: str = str(DATA_DIR / "google_calendar_mock.json")

    persist_raw_message_content: bool = False

    @field_validator("telegram_user_api_id", mode="before")
    @classmethod
    def _empty_string_to_none_int(cls, value):
        if value in ("", None):
            return None
        return value

    @field_validator("telegram_user_dialog_limit", "telegram_user_message_limit", mode="before")
    @classmethod
    def _empty_string_to_default_limit(cls, value, info):
        if value in ("", None):
            return 30 if info.field_name == "telegram_user_dialog_limit" else 100
        return value

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
