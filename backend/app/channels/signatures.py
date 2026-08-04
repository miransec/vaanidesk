"""HMAC signature verification with constant-time compare and replay protection."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time

from app.core.config import get_settings

logger = logging.getLogger(__name__)

REPLAY_STORE: dict[str, float] = {}


def _get_hmac_secret() -> bytes:
    settings = get_settings()
    return getattr(settings, "channel_hmac_secret", "dev-hmac-secret-not-for-production").encode()


def compute_signature(body: bytes, timestamp: str) -> str:
    secret = _get_hmac_secret()
    message = f"{timestamp}.{body.decode('utf-8', errors='replace')}".encode()
    return hmac.HMAC(secret, message, hashlib.sha256).hexdigest()


def verify_hmac(
    *,
    raw_body: bytes,
    signature: str,
    timestamp: str,
    event_id: str | None = None,
) -> bool:
    """Verify HMAC with constant-time compare, timestamp tolerance, and replay check.

    Returns True if valid, False otherwise. Fails closed on any issue.
    """
    settings = get_settings()
    tolerance = int(getattr(settings, "channel_signature_tolerance_seconds", 300))
    secret = _get_hmac_secret()

    if not signature or not timestamp:
        return False

    try:
        ts = int(timestamp)
    except (ValueError, TypeError):
        return False

    now = int(time.time())
    if abs(now - ts) > tolerance:
        logger.debug("signature_timestamp_stale delta=%d tolerance=%d", abs(now - ts), tolerance)
        return False

    message = f"{timestamp}.{raw_body.decode('utf-8', errors='replace')}".encode()
    expected = hmac.HMAC(secret, message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return False

    if event_id:
        replay_key = f"{event_id}:{timestamp}"
        if replay_key in REPLAY_STORE:
            logger.debug("signature_replay_detected event_id=%s", event_id)
            return False
        REPLAY_STORE[replay_key] = time.time()
        _cleanup_replay_store(tolerance * 2)

    return True


def _cleanup_replay_store(max_age: int) -> None:
    cutoff = time.time() - max_age
    stale = [k for k, v in REPLAY_STORE.items() if v < cutoff]
    for k in stale:
        del REPLAY_STORE[k]


def clear_replay_store() -> None:
    """For testing only."""
    REPLAY_STORE.clear()
