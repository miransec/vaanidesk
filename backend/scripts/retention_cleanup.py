"""Retention cleanup jobs — expire old audio, attachments, sessions, confirmations.

Usage: python -m scripts.retention_cleanup
Run as a periodic job (cron/systemd timer/k8s CronJob) or as the worker container.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def cleanup_expired_sessions() -> int:
    from app.database.session import SessionLocal
    from app.models.auth import RefreshSession
    from sqlalchemy import delete

    now = datetime.now(UTC)
    async with SessionLocal() as db:
        result = await db.execute(delete(RefreshSession).where(RefreshSession.expires_at < now))
        await db.commit()
        count = result.rowcount or 0
    logger.info("Cleaned up %d expired refresh sessions", count)
    return count


async def cleanup_old_audio(retention_hours: int = 72) -> int:
    audio_dir = os.environ.get("AUDIO_STORAGE_DIR", "./uploads/audio")
    path = Path(audio_dir)
    if not path.exists():
        return 0
    cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)
    removed = 0
    for f in path.iterdir():
        if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime, UTC) < cutoff:
            f.unlink(missing_ok=True)
            removed += 1
    logger.info("Removed %d audio files older than %dh", removed, retention_hours)
    return removed


async def cleanup_expired_confirmations() -> int:
    from app.core.redis import get_redis

    try:
        redis = await get_redis()
        keys = []
        async for key in redis.scan_iter("vd:confirm:*"):
            ttl = await redis.ttl(key)
            if ttl <= 0:
                keys.append(key)
        if keys:
            await redis.delete(*keys)
        logger.info("Cleaned up %d expired confirmation tokens", len(keys))
        return len(keys)
    except Exception as exc:
        logger.warning("Redis cleanup skipped: %s", exc)
        return 0


async def main() -> None:
    logger.info("Starting retention cleanup...")
    sessions = await cleanup_expired_sessions()
    audio = await cleanup_old_audio()
    confirmations = await cleanup_expired_confirmations()
    logger.info(
        "Cleanup complete: sessions=%d, audio=%d, confirmations=%d",
        sessions,
        audio,
        confirmations,
    )


if __name__ == "__main__":
    asyncio.run(main())
