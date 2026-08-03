from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("["):
            import json

            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [part.strip() for part in text.split(",") if part.strip()]
    raise TypeError(f"Unsupported CSV/list value: {type(value)!r}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VaaniDesk"
    app_env: Literal["development", "test", "production"] = "development"
    debug: bool = True
    secret_key: str = "change-me-to-a-long-random-string"
    api_prefix: str = "/api/v1"
    # Stored as CSV/JSON string in env; exposed as list via property helpers used by app.
    cors_origins: str = "http://localhost:3000"
    trusted_hosts: str = "localhost,127.0.0.1"
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"

    database_url: str = (
        "postgresql+asyncpg://vaanidesk:vaanidesk_dev_password@localhost:5432/vaanidesk"
    )
    redis_url: str = "redis://localhost:6379/0"
    redis_required_for_security: bool = True

    llm_provider: Literal["mock", "openai", "anthropic"] = "mock"
    embedding_provider: Literal["mock", "openai"] = "mock"
    stt_provider: Literal["mock"] = "mock"
    tts_provider: Literal["mock"] = "mock"
    vision_provider: Literal["mock"] = "mock"

    demo_mode: bool = True
    seed_on_startup: bool = False

    confirmation_token_ttl_seconds: int = 600
    idempotency_record_ttl_days: int = 30
    agent_confidence_escalate_threshold: float = 0.45

    def cors_origin_list(self) -> list[str]:
        return _split_csv(self.cors_origins)

    def trusted_host_list(self) -> list[str]:
        return _split_csv(self.trusted_hosts)


@lru_cache
def get_settings() -> Settings:
    return Settings()
