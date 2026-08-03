"""Redis-backed voice rate limits — fail closed when Redis unavailable."""

from __future__ import annotations

import logging

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


async def _incr_window(key: str, window_seconds: int, limit: int) -> None:
    try:
        client = await get_redis()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
        if count > limit:
            raise AppError(
                code="voice_rate_limited",
                message="Voice rate limit exceeded.",
                status_code=429,
            )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_rate_limit_redis_error error_type=%s", type(exc).__name__)
        raise AppError(
            code="voice_rate_limit_unavailable",
            message="Voice abuse protection unavailable (Redis).",
            status_code=503,
        ) from exc


async def check_upload_limits(
    *, user_id: str, size_bytes: int, settings: Settings | None = None
) -> None:
    cfg = settings or get_settings()
    await _incr_window(f"vd:voice:uploads:{user_id}", 60, cfg.voice_uploads_per_minute)
    try:
        client = await get_redis()
        bytes_key = f"vd:voice:bytes:{user_id}"
        total = await client.incrby(bytes_key, size_bytes)
        if total == size_bytes:
            await client.expire(bytes_key, 3600)
        if total > cfg.voice_bytes_per_hour:
            raise AppError(
                code="voice_bytes_limited",
                message="Voice upload byte quota exceeded for the current hour.",
                status_code=429,
            )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_bytes_limit_redis_error error_type=%s", type(exc).__name__)
        raise AppError(
            code="voice_rate_limit_unavailable",
            message="Voice abuse protection unavailable (Redis).",
            status_code=503,
        ) from exc


async def check_stt_limit(*, user_id: str, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    await _incr_window(f"vd:voice:stt:{user_id}", 60, cfg.stt_requests_per_minute)


async def check_tts_limit(*, user_id: str, settings: Settings | None = None) -> None:
    cfg = settings or get_settings()
    await _incr_window(f"vd:voice:tts:{user_id}", 60, cfg.tts_requests_per_minute)
