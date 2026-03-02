from pathlib import Path

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

    google_calendar_mock_path: str = str(DATA_DIR / "google_calendar_mock.json")

    persist_raw_message_content: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
