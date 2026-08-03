from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models import Conversation, Message, MessageRole, User
from app.providers.base import ChatMessage
from app.providers.factory import get_chat_provider
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ConversationDetail,
    ConversationSummary,
    MessageOut,
    ProviderMetadata,
)


async def create_chat_message(
    *,
    db: AsyncSession,
    user: User,
    payload: ChatMessageCreate,
    request_id: str,
) -> ChatMessageResponse:
    conversation = await _resolve_conversation(
        db=db, user=user, conversation_id=payload.conversation_id, first_message=payload.content
    )

    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=payload.content,
        request_id=request_id,
        provider_metadata=None,
    )
    db.add(user_message)
    await db.flush()

    provider = get_chat_provider()
    history = await _load_provider_history(db, conversation.id)
    completion = await provider.complete(messages=history, request_id=request_id)

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=completion.content,
        request_id=request_id,
        provider_metadata=completion.metadata,
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    provider_meta = ProviderMetadata(
        provider=completion.provider,
        model=completion.model,
        is_mock=completion.is_mock,
        language_hint=completion.language_hint,
        disclaimer=str(completion.metadata.get("disclaimer", "")),
        extra={k: v for k, v in completion.metadata.items() if k not in {"disclaimer"}},
    )
    return ChatMessageResponse(
        request_id=request_id,
        conversation_id=conversation.id,
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
        provider=provider_meta,
    )


async def list_conversations(*, db: AsyncSession, user: User) -> list[ConversationSummary]:
    stmt = (
        select(Conversation, func.count(Message.id))
        .outerjoin(Message, Message.conversation_id == Conversation.id)
        .where(Conversation.user_id == user.id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        ConversationSummary(
            id=conv.id,
            user_id=conv.user_id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=int(count or 0),
        )
        for conv, count in rows
    ]


async def get_conversation(
    *, db: AsyncSession, user: User, conversation_id: UUID
) -> ConversationDetail:
    stmt = (
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conversation = (await db.execute(stmt)).scalar_one_or_none()
    if conversation is None:
        raise AppError(
            code="conversation_not_found", message="Conversation not found.", status_code=404
        )
    if conversation.user_id != user.id:
        raise AppError(
            code="conversation_forbidden",
            message="You cannot access another user's conversation.",
            status_code=403,
        )
    return ConversationDetail(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[MessageOut.model_validate(m) for m in conversation.messages],
    )


async def _resolve_conversation(
    *,
    db: AsyncSession,
    user: User,
    conversation_id: UUID | None,
    first_message: str,
) -> Conversation:
    if conversation_id is None:
        title = first_message[:80]
        conversation = Conversation(user_id=user.id, title=title)
        db.add(conversation)
        await db.flush()
        return conversation

    found = await db.get(Conversation, conversation_id)
    if found is None:
        raise AppError(
            code="conversation_not_found", message="Conversation not found.", status_code=404
        )
    if found.user_id != user.id:
        raise AppError(
            code="conversation_forbidden",
            message="You cannot access another user's conversation.",
            status_code=403,
        )
    return found


async def _load_provider_history(db: AsyncSession, conversation_id: UUID) -> list[ChatMessage]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = (await db.execute(stmt)).scalars().all()
    return [ChatMessage(role=m.role.value, content=m.content) for m in messages]
