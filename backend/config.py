# ─────────────────────────────────────────────
#  Taskverse – Configuration Module
# ─────────────────────────────────────────────
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────
    telegram_bot_token: str = ""

    # ── Groq LLM ──────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama3-8b-8192"

    # ── MongoDB ───────────────────────────────
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "taskverse"

    # ── App ───────────────────────────────────
    app_env: Literal["development", "production", "testing"] = "development"
    log_level: str = "INFO"
    timezone: str = "Asia/Kolkata"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
