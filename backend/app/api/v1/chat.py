from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_request_id
from app.database.session import get_db
from app.models import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    ConversationDetail,
    ConversationSummary,
    DemoUserOut,
)
from app.services import chat as chat_service

router = APIRouter(tags=["chat"])


@router.get("/demo-users", response_model=list[DemoUserOut])
async def list_demo_users(db: AsyncSession = Depends(get_db)) -> list[DemoUserOut]:
    """List seeded demo users for the Phase 1 UI. Not production auth."""
    rows = (await db.execute(select(User).order_by(User.demo_key.asc()))).scalars().all()
    return [DemoUserOut.model_validate(u) for u in rows]


@router.post("/chat/messages", response_model=ChatMessageResponse)
async def post_chat_message(
    payload: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChatMessageResponse:
    return await chat_service.create_chat_message(
        db=db,
        user=user,
        payload=payload,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )


@router.post("/actions/confirm", response_model=ConfirmActionResponse)
async def post_confirm_action(
    payload: ConfirmActionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ConfirmActionResponse:
    return await chat_service.confirm_or_deny_action(
        db=db,
        user=user,
        payload=payload,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def get_conversations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ConversationSummary]:
    return await chat_service.list_conversations(db=db, user=user)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationDetail:
    return await chat_service.get_conversation(db=db, user=user, conversation_id=conversation_id)
