"""Redis-backed confirmation tokens — fail closed when Redis is unavailable.

Raw tokens are returned to the client once. Redis stores only SHA-256(token) as the key;
the payload never includes the raw token. Logs never include the raw token.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.redis import get_redis
from app.security.redaction import argument_hash

logger = logging.getLogger(__name__)

CONFIRM_PREFIX = "vd:confirm:"


def token_storage_key(raw_token: str) -> str:
    digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return f"{CONFIRM_PREFIX}{digest}"


@dataclass(frozen=True)
class ConfirmationPayload:
    token: str
    user_id: UUID
    tool_name: str
    argument_hash: str
    arguments: dict[str, Any]
    conversation_id: UUID
    request_id: str
    summary: str
    language_code: str
    expires_at: datetime
    idempotency_key: str | None = None


async def _redis_client() -> Redis[str]:
    from app.core.redis import reset_redis

    client = await get_redis()
    try:
        await client.ping()
        return client
    except RuntimeError:
        await reset_redis()
        return await get_redis()


async def create_confirmation(
    *,
    user_id: UUID,
    tool_name: str,
    arguments: dict[str, Any],
    conversation_id: UUID,
    request_id: str,
    summary: str,
    language_code: str,
    idempotency_key: str | None = None,
) -> ConfirmationPayload:
    settings = get_settings()
    ttl = int(getattr(settings, "confirmation_token_ttl_seconds", 600))
    token = secrets.token_urlsafe(32)
    arg_hash = argument_hash(arguments)
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
    # Payload intentionally omits the raw token.
    payload = {
        "user_id": str(user_id),
        "tool_name": tool_name,
        "argument_hash": arg_hash,
        "arguments": arguments,
        "conversation_id": str(conversation_id),
        "request_id": request_id,
        "summary": summary,
        "language_code": language_code,
        "expires_at": expires_at.isoformat(),
        "idempotency_key": idempotency_key,
    }
    try:
        client = await _redis_client()
        ok = await client.set(
            token_storage_key(token),
            json.dumps(payload),
            ex=ttl,
            nx=True,
        )
        if not ok:
            raise AppError(
                code="confirmation_store_failed",
                message="Could not store confirmation token.",
                status_code=503,
            )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "confirmation_redis_unavailable error_type=%s",
            type(exc).__name__,
        )
        raise AppError(
            code="confirmation_unavailable",
            message="Confirmation service unavailable. Sensitive actions are blocked.",
            status_code=503,
        ) from exc

    return ConfirmationPayload(
        token=token,
        user_id=user_id,
        tool_name=tool_name,
        argument_hash=arg_hash,
        arguments=arguments,
        conversation_id=conversation_id,
        request_id=request_id,
        summary=summary,
        language_code=language_code,
        expires_at=expires_at,
        idempotency_key=idempotency_key,
    )


async def consume_confirmation(
    *,
    token: str,
    user_id: UUID,
) -> ConfirmationPayload:
    """Load and delete a one-time confirmation token (fail closed)."""
    try:
        client = await _redis_client()
        key = token_storage_key(token)
        raw = await client.get(key)
        if raw is None:
            raise AppError(
                code="confirmation_invalid",
                message="Confirmation token is invalid or expired.",
                status_code=400,
            )
        data = json.loads(raw)
        if UUID(data["user_id"]) != user_id:
            raise AppError(
                code="confirmation_forbidden",
                message="Confirmation token does not belong to this user.",
                status_code=403,
            )
        expires_at = datetime.fromisoformat(data["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            await client.delete(key)
            raise AppError(
                code="confirmation_expired",
                message="Confirmation token has expired.",
                status_code=400,
            )
        deleted = await client.delete(key)
        if not deleted:
            raise AppError(
                code="confirmation_invalid",
                message="Confirmation token is invalid or expired.",
                status_code=400,
            )
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "confirmation_redis_unavailable error_type=%s",
            type(exc).__name__,
        )
        raise AppError(
            code="confirmation_unavailable",
            message="Confirmation service unavailable. Sensitive actions are blocked.",
            status_code=503,
        ) from exc

    return ConfirmationPayload(
        token="[consumed]",
        user_id=UUID(data["user_id"]),
        tool_name=data["tool_name"],
        argument_hash=data["argument_hash"],
        arguments=data["arguments"],
        conversation_id=UUID(data["conversation_id"]),
        request_id=data["request_id"],
        summary=data["summary"],
        language_code=data.get("language_code", "en"),
        expires_at=expires_at,
        idempotency_key=data.get("idempotency_key"),
    )


async def deny_confirmation(*, token: str, user_id: UUID) -> None:
    """Invalidate a token without executing the action."""
    try:
        client = await _redis_client()
        key = token_storage_key(token)
        raw = await client.get(key)
        if raw is None:
            raise AppError(
                code="confirmation_invalid",
                message="Confirmation token is invalid or expired.",
                status_code=400,
            )
        data = json.loads(raw)
        if UUID(data["user_id"]) != user_id:
            raise AppError(
                code="confirmation_forbidden",
                message="Confirmation token does not belong to this user.",
                status_code=403,
            )
        await client.delete(key)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "confirmation_redis_unavailable error_type=%s",
            type(exc).__name__,
        )
        raise AppError(
            code="confirmation_unavailable",
            message="Confirmation service unavailable. Sensitive actions are blocked.",
            status_code=503,
        ) from exc
