"""Inbound message processing pipeline."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import ChannelAdapter, NormalizedMessage, NormalizedSender
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Conversation, Message, MessageRole, User
from app.models.channels import (
    ChannelConnection,
    ChannelIdentity,
    ConversationChannel,
    InboundEvent,
    InboundEventStatus,
    VerificationStatus,
)
from app.workflows.orchestrator import run_support_workflow

logger = logging.getLogger(__name__)


def _hash_event(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()[:64]


async def process_inbound(
    *,
    db: AsyncSession,
    adapter: ChannelAdapter,
    connection: ChannelConnection,
    raw_body: bytes,
    headers: dict[str, str],
    external_event_id: str,
) -> dict[str, Any]:
    """Full inbound pipeline: size→verify→parse→dedupe→normalize→identity→orchestrator."""
    settings = get_settings()
    max_bytes = int(getattr(settings, "channel_webhook_max_bytes", 1_048_576))

    if len(raw_body) > max_bytes:
        raise AppError(
            code="payload_too_large", message="Webhook payload exceeds size limit.", status_code=413
        )

    if not adapter.verify_signature(raw_body, headers):
        raise AppError(
            code="signature_invalid",
            message="Webhook signature verification failed.",
            status_code=401,
        )

    event_hash = _hash_event(raw_body)

    event = InboundEvent(
        id=uuid4(),
        channel_connection_id=connection.id,
        external_event_id=external_event_id,
        event_hash=event_hash,
        status=InboundEventStatus.PROCESSING,
    )
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
    except IntegrityError:
        return {"status": "duplicate", "event_id": external_event_id}

    try:
        import json

        payload = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError) as exc:
        event.status = InboundEventStatus.REJECTED
        event.error_code = "invalid_payload"
        await db.flush()
        raise AppError(
            code="invalid_payload", message="Could not parse webhook body.", status_code=400
        ) from exc

    sender = adapter.normalize_sender(payload)
    message = adapter.normalize_message(payload)

    identity = await _resolve_identity(db=db, connection=connection, sender=sender)
    user = await _resolve_user(db=db, identity=identity)

    if user is None:
        event.status = InboundEventStatus.PROCESSED
        event.processed_at = datetime.now(UTC)
        event.safe_metadata = {"anonymous": True, "text_length": len(message.text)}
        await db.flush()
        return {
            "status": "anonymous_ack",
            "event_id": external_event_id,
            "note": "Identity not linked — limited support only",
        }

    conversation = await _resolve_conversation(
        db=db, user=user, identity=identity, connection=connection, message=message
    )

    request_id = f"ch-{uuid4().hex[:12]}"
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=message.text,
        request_id=request_id,
    )
    db.add(user_msg)
    await db.flush()

    result = await run_support_workflow(
        db=db,
        user=user,
        conversation_id=conversation.id,
        message_id=user_msg.id,
        text=message.text,
        request_id=request_id,
    )

    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result.assistant_text,
        request_id=request_id,
        provider_metadata={"channel": adapter.channel_type, "is_mock": True},
    )
    db.add(assistant_msg)

    event.status = InboundEventStatus.PROCESSED
    event.processed_at = datetime.now(UTC)
    event.normalized_message_id = user_msg.id
    event.safe_metadata = {"text_length": len(message.text), "channel": adapter.channel_type}

    await db.commit()

    return {
        "status": "processed",
        "event_id": external_event_id,
        "conversation_id": str(conversation.id),
        "assistant_text": result.assistant_text,
    }


async def _resolve_identity(
    *,
    db: AsyncSession,
    connection: ChannelConnection,
    sender: NormalizedSender,
) -> ChannelIdentity:
    stmt = select(ChannelIdentity).where(
        ChannelIdentity.channel_connection_id == connection.id,
        ChannelIdentity.external_sender_id_hash == sender.external_id_hash,
    )
    identity = (await db.execute(stmt)).scalar_one_or_none()
    if identity is None:
        identity = ChannelIdentity(
            id=uuid4(),
            channel_connection_id=connection.id,
            external_sender_id_hash=sender.external_id_hash,
            external_sender_display=sender.display_name,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        db.add(identity)
        await db.flush()
    return identity


async def _resolve_user(*, db: AsyncSession, identity: ChannelIdentity) -> User | None:
    if identity.user_id is None:
        return None
    return await db.get(User, identity.user_id)


async def _resolve_conversation(
    *,
    db: AsyncSession,
    user: User,
    identity: ChannelIdentity,
    connection: ChannelConnection,
    message: NormalizedMessage,
) -> Conversation:
    stmt = (
        select(ConversationChannel)
        .where(
            ConversationChannel.channel_connection_id == connection.id,
            ConversationChannel.channel_identity_id == identity.id,
        )
        .order_by(ConversationChannel.created_at.desc())
        .limit(1)
    )
    link = (await db.execute(stmt)).scalar_one_or_none()

    if link is not None:
        conv = await db.get(Conversation, link.conversation_id)
        if conv is not None:
            return conv

    conversation = Conversation(
        id=uuid4(),
        user_id=user.id,
        title=message.text[:80],
    )
    db.add(conversation)
    await db.flush()

    chan_link = ConversationChannel(
        id=uuid4(),
        conversation_id=conversation.id,
        channel_connection_id=connection.id,
        channel_identity_id=identity.id,
    )
    db.add(chan_link)
    await db.flush()
    return conversation
