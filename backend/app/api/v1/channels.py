"""Phase 5 — Omnichannel API router."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models import User
from app.schemas.channels import (
    ChannelAttachmentOut,
    ChannelConnectionOut,
    ChannelConnectionToggle,
    ExternalConfirmationOut,
    ExternalConfirmRequest,
    HandoffAssignRequest,
    HandoffQueueItemOut,
    InboundEventOut,
    LinkChallengeCreate,
    LinkChallengeResponse,
    LinkCompleteRequest,
    LinkCompleteResponse,
    OutboundMessageOut,
    SimulatorEmailEvent,
    SimulatorWhatsAppEvent,
    UnlinkRequest,
)
from app.services import channels as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["channels"])


# --- Connections ---


@router.get("/connections", response_model=list[ChannelConnectionOut])
async def list_connections(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    conns = await svc.list_connections(db=db)
    return conns


@router.post("/connections/{connection_id}/toggle", response_model=ChannelConnectionOut)
async def toggle_connection(
    connection_id: UUID,
    body: ChannelConnectionToggle,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    conn = await svc.toggle_connection(db=db, connection_id=connection_id, enabled=body.enabled)
    await db.commit()
    return conn


# --- Webhooks ---


@router.post("/webhook/email")
async def webhook_email(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    event_id = headers.get("x-channel-event-id", "")
    result = await svc.process_webhook(
        db=db, channel_type="email", raw_body=raw_body, headers=headers, external_event_id=event_id
    )
    await db.commit()
    return result


@router.post("/webhook/whatsapp")
async def webhook_whatsapp(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    event_id = headers.get("x-channel-event-id", "")
    result = await svc.process_webhook(
        db=db,
        channel_type="whatsapp",
        raw_body=raw_body,
        headers=headers,
        external_event_id=event_id,
    )
    await db.commit()
    return result


@router.get("/webhook/whatsapp")
async def webhook_whatsapp_verify(
    request: Request,
) -> PlainTextResponse:
    """WhatsApp verification challenge GET endpoint."""
    from app.channels.whatsapp.adapter import WhatsAppAdapter

    adapter = WhatsAppAdapter()
    params = dict(request.query_params)
    challenge = adapter.verify_webhook_challenge(params)
    if challenge:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Verification failed", status_code=403)


# --- Simulator ---


@router.post("/simulator/email")
async def simulator_email(
    body: SimulatorEmailEvent,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    event = {
        "from": body.from_email,
        "from_display": body.from_display,
        "subject": body.subject,
        "text_body": body.text_body,
        "message_id": body.message_id,
    }
    result = await svc.process_simulator_email(db=db, event=event)
    await db.commit()
    return result


@router.post("/simulator/whatsapp")
async def simulator_whatsapp(
    body: SimulatorWhatsAppEvent,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    result = await svc.process_simulator_whatsapp(
        db=db,
        from_phone=body.from_phone,
        display_name=body.display_name,
        text=body.text,
        message_id=body.message_id,
    )
    await db.commit()
    return result


# --- Identity Linking ---


@router.post("/identity/link", response_model=LinkChallengeResponse)
async def create_link(
    body: LinkChallengeCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    from app.channels.linking import create_link_challenge

    result = await create_link_challenge(
        db=db, channel_identity_id=body.channel_identity_id, user_id=user.id
    )
    await db.commit()
    return result


@router.post("/identity/link/complete", response_model=LinkCompleteResponse)
async def complete_link(
    body: LinkCompleteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    from app.channels.linking import complete_link_challenge

    result = await complete_link_challenge(db=db, token=body.token, user_id=user.id)
    await db.commit()
    return result


@router.post("/identity/unlink")
async def unlink(
    body: UnlinkRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    from app.channels.linking import unlink_identity

    result = await unlink_identity(db=db, identity_id=body.identity_id, user_id=user.id)
    await db.commit()
    return result


# --- External Confirmation ---


@router.get("/confirm")
async def get_confirmation(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExternalConfirmationOut:
    ecr = await svc.get_external_confirmation(db=db, token=token, user_id=user.id)
    return ExternalConfirmationOut.model_validate(ecr)


@router.post("/confirm")
async def confirm_action(
    token: str = Query(...),
    body: ExternalConfirmRequest = ExternalConfirmRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    result = await svc.confirm_external_action(
        db=db, token=token, user_id=user.id, approved=body.approved
    )
    await db.commit()
    return result


# --- Outbound ---


@router.get("/outbound/failed", response_model=list[OutboundMessageOut])
async def list_failed_outbound(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    return await svc.list_failed_outbound(db=db)


@router.post("/outbound/{message_id}/retry")
async def retry_outbound(
    message_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    result = await svc.retry_outbound_message(db=db, message_id=message_id)
    await db.commit()
    return result


# --- Handoff Queue ---


@router.get("/handoff", response_model=list[HandoffQueueItemOut])
async def list_handoff(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    from app.models.channels import HandoffStatus as HS

    filter_status = HS(status) if status else None
    items = (
        await svc.list_handoff_queue(db=db)
        if not filter_status
        else await svc.list_handoff_queue(db=db)
    )
    if filter_status:
        from app.channels.handoff import list_handoff_queue

        items = await list_handoff_queue(db=db, status_filter=filter_status)
    return items


@router.post("/handoff/{handoff_id}/assign", response_model=HandoffQueueItemOut)
async def assign_handoff_endpoint(
    handoff_id: UUID,
    body: HandoffAssignRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    from app.channels.handoff import assign_handoff

    item = await assign_handoff(db=db, handoff_id=handoff_id, agent_id=body.agent_id)
    await db.commit()
    return item


# --- Inbound Events ---


@router.get("/events", response_model=list[InboundEventOut])
async def list_events(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    return await svc.list_inbound_events(db=db)


# --- Attachments ---


@router.get("/attachments/{attachment_id}", response_model=ChannelAttachmentOut)
async def get_attachment(
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Any:
    return await svc.get_attachment(db=db, attachment_id=attachment_id, user_id=user.id)


# --- Seed (for dev) ---


@router.post("/seed")
async def seed_connections(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    conns = await svc.seed_default_connections(db=db)
    await db.commit()
    return {"seeded": len(conns)}
