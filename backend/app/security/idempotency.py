"""Durable Postgres idempotency records for state-changing tools."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import IdempotencyRecord, IdempotencyState
from app.security.redaction import argument_hash


async def begin_or_replay(
    *,
    db: AsyncSession,
    user_id: UUID,
    tool_name: str,
    arguments: dict[str, Any],
    idempotency_key: str,
) -> tuple[IdempotencyRecord | None, dict[str, Any] | None]:
    """Return (record_to_complete, replay_result).

    Concurrent inserts on the unique key become in_progress / replay without
    aborting the outer transaction (savepoint).
    """
    settings = get_settings()
    ttl_days = int(getattr(settings, "idempotency_record_ttl_days", 30))
    arg_hash = argument_hash(arguments)

    async def _load_existing() -> IdempotencyRecord | None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == idempotency_key,
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.tool_name == tool_name,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    existing = await _load_existing()
    if existing is not None:
        return await _handle_existing(existing, arg_hash=arg_hash, ttl_days=ttl_days, db=db)

    record = IdempotencyRecord(
        id=uuid4(),
        idempotency_key=idempotency_key,
        user_id=user_id,
        tool_name=tool_name,
        argument_hash=arg_hash,
        state=IdempotencyState.IN_PROGRESS,
        expires_at=datetime.now(UTC) + timedelta(days=ttl_days),
    )
    try:
        async with db.begin_nested():
            db.add(record)
            await db.flush()
    except IntegrityError as exc:
        raced = await _load_existing()
        if raced is None:
            raise AppError(
                code="idempotency_conflict",
                message="Idempotency race could not be resolved.",
                status_code=409,
            ) from exc
        return await _handle_existing(raced, arg_hash=arg_hash, ttl_days=ttl_days, db=db)
    return record, None


async def _handle_existing(
    existing: IdempotencyRecord,
    *,
    arg_hash: str,
    ttl_days: int,
    db: AsyncSession,
) -> tuple[IdempotencyRecord | None, dict[str, Any] | None]:
    if existing.argument_hash != arg_hash:
        raise AppError(
            code="idempotency_conflict",
            message="Idempotency key reused with different arguments.",
            status_code=409,
        )
    if existing.state == IdempotencyState.COMPLETED and existing.result is not None:
        return None, existing.result
    if existing.state == IdempotencyState.IN_PROGRESS:
        raise AppError(
            code="idempotency_in_progress",
            message="A request with this idempotency key is already in progress.",
            status_code=409,
        )
    if existing.state == IdempotencyState.FAILED:
        existing.state = IdempotencyState.IN_PROGRESS
        existing.error_result = None
        existing.expires_at = datetime.now(UTC) + timedelta(days=ttl_days)
        await db.flush()
        return existing, None
    raise AppError(
        code="idempotency_conflict",
        message="Idempotency record is in an unexpected state.",
        status_code=409,
    )


async def complete_record(
    *,
    record: IdempotencyRecord,
    result: dict[str, Any],
) -> None:
    record.state = IdempotencyState.COMPLETED
    record.result = result


async def fail_record(
    *,
    record: IdempotencyRecord,
    error: dict[str, Any],
) -> None:
    record.state = IdempotencyState.FAILED
    record.error_result = error
