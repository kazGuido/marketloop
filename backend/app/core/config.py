from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Deterministic Harmonic Sentinel"
    environment: Literal["local", "test", "production"] = "local"

    database_url: str = "postgresql+asyncpg://sentinel:sentinel@postgres:5432/sentinel"
    redis_url: str = "redis://redis:6379/0"

    hyperliquid_info_url: str = "https://api.hyperliquid.xyz/info"
    hyperliquid_api_url: str = "https://api.hyperliquid.xyz"
    hyperliquid_wallet_address: str | None = None
    hyperliquid_private_key: str | None = None

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    default_timeframe: str = "15m"
    candle_lookback_minutes: int = 60 * 24 * 7
    collector_interval_seconds: int = 60
    scanner_interval_seconds: int = 60
    confluence_interval_seconds: int = 10
    risk_interval_seconds: int = 15
    max_assets_per_cycle: int = 25

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
