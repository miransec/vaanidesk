"""Phase 5 — Channel services: business logic + authorization."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.attachments import authorize_download
from app.channels.email.adapter import EmailAdapter
from app.channels.handoff import (
    list_handoff_queue as _list_handoff_queue,
)
from app.channels.pipeline import process_inbound
from app.channels.whatsapp.adapter import WhatsAppAdapter
from app.core.config import get_settings
from app.core.errors import AppError
from app.models.channels import (
    ChannelAttachment,
    ChannelConnection,
    ChannelType,
    ExternalConfirmationRequest,
    ExternalConfirmStatus,
    HumanHandoffQueueItem,
    InboundEvent,
    OutboundMessage,
    OutboundMessageStatus,
)

logger = logging.getLogger(__name__)


def _get_adapter(channel_type: str) -> EmailAdapter | WhatsAppAdapter:
    if channel_type == "email":
        return EmailAdapter()
    if channel_type == "whatsapp":
        return WhatsAppAdapter()
    raise AppError(
        code="unsupported_channel",
        message=f"Channel type '{channel_type}' not supported.",
        status_code=400,
    )


async def list_connections(*, db: AsyncSession) -> list[ChannelConnection]:
    stmt = select(ChannelConnection).order_by(ChannelConnection.created_at.asc())
    return list((await db.execute(stmt)).scalars().all())


async def toggle_connection(
    *, db: AsyncSession, connection_id: UUID, enabled: bool
) -> ChannelConnection:
    conn = await db.get(ChannelConnection, connection_id)
    if conn is None:
        raise AppError(
            code="connection_not_found", message="Channel connection not found.", status_code=404
        )
    conn.enabled = enabled
    conn.updated_at = datetime.now(UTC)
    await db.flush()
    return conn


async def process_webhook(
    *,
    db: AsyncSession,
    channel_type: str,
    raw_body: bytes,
    headers: dict[str, str],
    external_event_id: str,
) -> dict[str, Any]:
    """Process an inbound webhook for a channel type."""
    stmt = (
        select(ChannelConnection)
        .where(
            ChannelConnection.channel_type == channel_type,
            ChannelConnection.enabled == True,  # noqa: E712
        )
        .limit(1)
    )
    connection = (await db.execute(stmt)).scalar_one_or_none()
    if connection is None:
        raise AppError(
            code="channel_not_configured",
            message=f"No active {channel_type} channel.",
            status_code=404,
        )

    adapter = _get_adapter(channel_type)
    return await process_inbound(
        db=db,
        adapter=adapter,
        connection=connection,
        raw_body=raw_body,
        headers=headers,
        external_event_id=external_event_id,
    )


async def process_simulator_email(
    *,
    db: AsyncSession,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Process a simulated email event."""
    import json
    import time

    from app.channels.signatures import compute_signature

    body = json.dumps(event).encode()
    timestamp = str(int(time.time()))
    signature = compute_signature(body, timestamp)
    event_id = event.get("message_id") or f"sim-email-{uuid4().hex[:8]}"

    headers = {
        "x-channel-signature": signature,
        "x-channel-timestamp": timestamp,
        "x-channel-event-id": event_id,
        "content-type": "application/json",
    }

    return await process_webhook(
        db=db,
        channel_type="email",
        raw_body=body,
        headers=headers,
        external_event_id=event_id,
    )


async def process_simulator_whatsapp(
    *,
    db: AsyncSession,
    from_phone: str,
    display_name: str,
    text: str,
    message_id: str | None = None,
) -> dict[str, Any]:
    """Process a simulated WhatsApp event."""
    from app.channels.whatsapp.simulator import create_simulator_webhook

    body, headers = create_simulator_webhook(
        from_phone=from_phone,
        display_name=display_name,
        text=text,
        message_id=message_id,
    )
    event_id = headers.get("x-channel-event-id", f"sim-wa-{uuid4().hex[:8]}")

    return await process_webhook(
        db=db,
        channel_type="whatsapp",
        raw_body=body,
        headers=headers,
        external_event_id=event_id,
    )


async def create_external_confirmation(
    *,
    db: AsyncSession,
    user_id: UUID,
    channel_identity_id: UUID,
    action: str,
    action_args: dict[str, Any],
    summary: str,
    conversation_id: UUID | None = None,
) -> dict[str, Any]:
    """Create a signed one-time web confirmation for sensitive channel actions."""
    settings = get_settings()
    ttl = int(getattr(settings, "channel_external_confirm_ttl_seconds", 600))
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    ecr = ExternalConfirmationRequest(
        id=uuid4(),
        token_hash=token_hash,
        channel_identity_id=channel_identity_id,
        user_id=user_id,
        action=action,
        action_args=action_args,
        summary=summary,
        status=ExternalConfirmStatus.PENDING,
        conversation_id=conversation_id,
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
    )
    db.add(ecr)
    await db.flush()

    frontend_url = getattr(settings, "frontend_url", "http://localhost:3000")
    confirm_url = f"{frontend_url}/channels/confirm?token={token}"

    return {
        "confirmation_id": str(ecr.id),
        "url": confirm_url,
        "expires_in_seconds": ttl,
        "token": token,
    }


async def get_external_confirmation(
    *,
    db: AsyncSession,
    token: str,
    user_id: UUID,
) -> ExternalConfirmationRequest:
    """Get confirmation request by token (for display)."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(ExternalConfirmationRequest).where(
        ExternalConfirmationRequest.token_hash == token_hash
    )
    ecr = (await db.execute(stmt)).scalar_one_or_none()
    if ecr is None:
        raise AppError(
            code="confirmation_not_found", message="Confirmation not found.", status_code=404
        )
    if ecr.user_id != user_id:
        raise AppError(
            code="confirmation_forbidden", message="Not your confirmation.", status_code=403
        )
    return ecr


async def confirm_external_action(
    *,
    db: AsyncSession,
    token: str,
    user_id: UUID,
    approved: bool = True,
) -> dict[str, str]:
    """Confirm or deny an external action."""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    stmt = select(ExternalConfirmationRequest).where(
        ExternalConfirmationRequest.token_hash == token_hash
    )
    ecr = (await db.execute(stmt)).scalar_one_or_none()
    if ecr is None:
        raise AppError(
            code="confirmation_not_found", message="Confirmation not found.", status_code=404
        )
    if ecr.user_id != user_id:
        raise AppError(
            code="confirmation_forbidden", message="Not your confirmation.", status_code=403
        )
    if ecr.status != ExternalConfirmStatus.PENDING:
        raise AppError(
            code="confirmation_already_resolved", message="Already resolved.", status_code=400
        )
    if ecr.expires_at < datetime.now(UTC):
        ecr.status = ExternalConfirmStatus.EXPIRED
        await db.flush()
        raise AppError(
            code="confirmation_expired", message="Confirmation has expired.", status_code=400
        )

    if approved:
        ecr.status = ExternalConfirmStatus.CONFIRMED
        ecr.confirmed_at = datetime.now(UTC)
    else:
        ecr.status = ExternalConfirmStatus.DENIED

    await db.flush()
    return {"status": ecr.status.value, "confirmation_id": str(ecr.id)}


async def list_failed_outbound(*, db: AsyncSession) -> list[OutboundMessage]:
    stmt = (
        select(OutboundMessage)
        .where(
            OutboundMessage.status.in_(
                [OutboundMessageStatus.FAILED, OutboundMessageStatus.DEAD_LETTER]
            )
        )
        .order_by(OutboundMessage.failed_at.desc())
        .limit(50)
    )
    return list((await db.execute(stmt)).scalars().all())


async def retry_outbound_message(*, db: AsyncSession, message_id: UUID) -> dict[str, str]:
    msg = await db.get(OutboundMessage, message_id)
    if msg is None:
        raise AppError(
            code="message_not_found", message="Outbound message not found.", status_code=404
        )
    if msg.status == OutboundMessageStatus.DEAD_LETTER:
        raise AppError(
            code="message_dead_letter", message="Cannot retry dead-letter message.", status_code=400
        )
    msg.status = OutboundMessageStatus.QUEUED
    msg.failed_at = None
    await db.flush()
    return {"status": "requeued", "message_id": str(msg.id)}


async def list_inbound_events(*, db: AsyncSession, limit: int = 50) -> list[InboundEvent]:
    stmt = select(InboundEvent).order_by(InboundEvent.received_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def get_attachment(
    *, db: AsyncSession, attachment_id: UUID, user_id: UUID
) -> ChannelAttachment:
    att = await db.get(ChannelAttachment, attachment_id)
    if att is None:
        raise AppError(
            code="attachment_not_found", message="Attachment not found.", status_code=404
        )
    if not authorize_download(owner_user_id=att.owner_user_id, requesting_user_id=user_id):
        raise AppError(code="attachment_forbidden", message="Access denied.", status_code=403)
    return att


async def seed_default_connections(*, db: AsyncSession) -> list[ChannelConnection]:
    """Idempotent seed for default channel connections."""
    existing = (await db.execute(select(ChannelConnection))).scalars().all()
    if existing:
        return list(existing)

    connections = [
        ChannelConnection(
            id=uuid4(),
            channel_type=ChannelType.WEB,
            display_name="Web Chat (built-in)",
            enabled=True,
            configuration_reference="builtin:web",
        ),
        ChannelConnection(
            id=uuid4(),
            channel_type=ChannelType.EMAIL,
            display_name="Email Dev Inbox",
            enabled=True,
            configuration_reference="dev:email",
        ),
        ChannelConnection(
            id=uuid4(),
            channel_type=ChannelType.WHATSAPP,
            display_name="WhatsApp Simulator",
            enabled=True,
            configuration_reference="simulator:whatsapp",
        ),
    ]
    for c in connections:
        db.add(c)
    await db.flush()
    return connections


async def list_handoff_queue(*, db: AsyncSession) -> list[HumanHandoffQueueItem]:
    return await _list_handoff_queue(db=db)
