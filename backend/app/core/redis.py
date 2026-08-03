from __future__ import annotations

import logging
from typing import Protocol

from redis.asyncio import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis: Redis[str] | None = None


async def get_redis() -> Redis[str]:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.close()
        _redis = None


async def check_redis() -> tuple[bool, str | None]:
    try:
        client = await get_redis()
        pong = await client.ping()
        if pong:
            return True, None
        return False, "ping_failed"
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis_check_failed error_type=%s", type(exc).__name__)
        return False, type(exc).__name__


class RedisClient(Protocol):
    async def ping(self) -> bool: ...
