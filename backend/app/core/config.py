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
    # Directory containing policies/manifest.json. Empty/unset → host repo fallback.
    # Compose sets /sample_data/policies with ./sample_data mounted at /sample_data.
    knowledge_seed_dir: str | None = None

    confirmation_token_ttl_seconds: int = 600
    idempotency_record_ttl_days: int = 30
    agent_confidence_escalate_threshold: float = 0.45
    rag_min_retrieval_confidence: float = 0.30
    max_knowledge_upload_bytes: int = 512000

    # Phase 5 — omnichannel
    channels_enabled: bool = True
    email_adapter_enabled: bool = True
    whatsapp_enabled: bool = False
    channel_webhook_max_bytes: int = 1_048_576
    channel_signature_tolerance_seconds: int = 300
    channel_link_challenge_ttl_seconds: int = 600
    channel_external_confirm_ttl_seconds: int = 600
    channel_attachment_max_bytes: int = 10_485_760
    channel_outbox_max_attempts: int = 5
    channel_hmac_secret: str = "dev-hmac-secret-not-for-production"

    # Phase 6 — evaluations / observability
    otel_enabled: bool = False
    otel_exporter: str = "console"
    otel_service_name: str = "vaanidesk-backend"
    metrics_enabled: bool = True
    eval_default_provider: str = "mock"
    eval_default_seed: int = 42
    eval_default_timeout: int = 60
    eval_max_concurrency: int = 8
    alert_error_rate_threshold: float = 0.10
    alert_latency_p95_threshold_ms: float = 5000.0
    alert_provider_failure_threshold: float = 0.50
    alert_eval_window_seconds: int = 300

    # Phase 4 — voice / audio
    voice_enabled: bool = True
    voice_auto_submit_enabled: bool = True
    audio_storage_dir: str = "./uploads/audio"
    audio_retention_hours: int = 72
    audio_max_size_bytes: int = 10_485_760
    audio_max_duration_seconds: int = 120
    audio_allowed_formats: str = "wav,mp3,webm,m4a"
    audio_processing_timeout_seconds: int = 30
    stt_min_auto_submit_confidence: float = 0.85
    voice_uploads_per_minute: int = 20
    voice_bytes_per_hour: int = 52_428_800
    stt_requests_per_minute: int = 30
    tts_requests_per_minute: int = 30
    voice_max_concurrent_jobs: int = 4

    def cors_origin_list(self) -> list[str]:
        return _split_csv(self.cors_origins)

    def trusted_host_list(self) -> list[str]:
        return _split_csv(self.trusted_hosts)

    def audio_allowed_formats_list(self) -> list[str]:
        return _split_csv(self.audio_allowed_formats)


@lru_cache
def get_settings() -> Settings:
    return Settings()
