"""Transactional outbox worker functions for outbound message delivery."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import ChannelAdapter, DeliveryResult, OutboundPayload
from app.core.config import get_settings
from app.models.channels import (
    DeliveryAttempt,
    OutboundMessage,
    OutboundMessageStatus,
)

logger = logging.getLogger(__name__)


async def deliver_message(
    *,
    db: AsyncSession,
    message: OutboundMessage,
    adapter: ChannelAdapter,
    recipient_external_id: str,
) -> DeliveryResult:
    """Attempt delivery of a queued outbound message."""
    settings = get_settings()
    max_attempts = int(getattr(settings, "channel_outbox_max_attempts", 5))

    message.status = OutboundMessageStatus.SENDING
    await db.flush()

    payload = OutboundPayload(
        recipient_id=recipient_external_id,
        content=message.rendered_content,
        message_type=message.message_type.value,
    )

    result = await adapter.send_message(payload)

    attempt = DeliveryAttempt(
        id=uuid4(),
        outbound_message_id=message.id,
        attempt_number=await _get_attempt_count(db, message.id) + 1,
        provider_status=result.provider_status,
        provider_message_id_hash=result.provider_message_id,
        response_code=result.response_code,
        error_code=result.error_code,
    )

    if result.success:
        message.status = OutboundMessageStatus.SENT
        message.sent_at = datetime.now(UTC)
    else:
        if attempt.attempt_number >= max_attempts:
            message.status = OutboundMessageStatus.DEAD_LETTER
            message.failed_at = datetime.now(UTC)
        else:
            message.status = OutboundMessageStatus.FAILED
            message.failed_at = datetime.now(UTC)
            attempt.next_retry_at = datetime.now(UTC) + timedelta(
                seconds=min(60 * (2**attempt.attempt_number), 3600)
            )

    db.add(attempt)
    await db.flush()
    return result


async def retry_failed_messages(
    *,
    db: AsyncSession,
    adapter: ChannelAdapter,
    recipient_external_id: str,
    limit: int = 10,
) -> int:
    """Retry failed (non-dead-letter) outbound messages. Returns count retried."""
    stmt = (
        select(OutboundMessage)
        .where(OutboundMessage.status == OutboundMessageStatus.FAILED)
        .order_by(OutboundMessage.failed_at.asc())
        .limit(limit)
    )
    messages = (await db.execute(stmt)).scalars().all()
    retried = 0
    for msg in messages:
        msg.status = OutboundMessageStatus.QUEUED
        msg.failed_at = None
        await deliver_message(
            db=db, message=msg, adapter=adapter, recipient_external_id=recipient_external_id
        )
        retried += 1
    return retried


async def _get_attempt_count(db: AsyncSession, outbound_id: object) -> int:
    from sqlalchemy import func

    stmt = select(func.count()).where(DeliveryAttempt.outbound_message_id == outbound_id)
    return int((await db.execute(stmt)).scalar_one())
