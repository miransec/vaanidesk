from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.intent import Intent, IntentResult
from app.agents.language import LanguageResult
from app.agents.responses import respond
from app.core.errors import AppError
from app.models import Conversation, Message, MessageRole, User, WorkflowStatus
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ConfirmActionRequest,
    ConfirmActionResponse,
    ConfirmationOut,
    ConversationDetail,
    ConversationSummary,
    MessageOut,
    ProviderMetadata,
    WorkflowOut,
)
from app.security.confirmation import consume_confirmation
from app.security.redaction import argument_hash
from app.workflows.orchestrator import execute_tool_and_respond, run_support_workflow
from app.workflows.types import WorkflowResult


def _provider_meta(language_hint: str | None = None) -> ProviderMetadata:
    return ProviderMetadata(
        provider="workflow-heuristic",
        model="vaanidesk-phase2-workflow",
        is_mock=True,
        language_hint=language_hint,
        disclaimer="Phase 2 controlled workflow — not a production LLM",
        extra={},
    )


def _workflow_out(result: WorkflowResult) -> WorkflowOut:
    confirmation = None
    if result.confirmation is not None:
        confirmation = ConfirmationOut(
            token=result.confirmation.token,
            action=result.confirmation.action,
            summary=result.confirmation.summary,
            expires_at=result.confirmation.expires_at,
        )
    return WorkflowOut(
        status=result.status.value,
        detected_language=result.language_code,
        script=result.script,
        intent=result.intent,
        intent_confidence=result.intent_confidence,
        selected_tool=result.selected_tool,
        tool_execution_status=result.tool_execution_status,
        clarification_required=result.clarification_required,
        confirmation_required=result.confirmation_required,
        escalation_required=result.escalation_required,
        escalation_reason=result.escalation_reason,
        trace_id=result.trace_id,
        confirmation=confirmation,
    )


async def create_chat_message(
    *,
    db: AsyncSession,
    user: User,
    payload: ChatMessageCreate,
    request_id: str,
    idempotency_key: str | None = None,
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

    result = await run_support_workflow(
        db=db,
        user=user,
        conversation_id=conversation.id,
        message_id=user_message.id,
        text=payload.content,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )

    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result.assistant_text,
        request_id=request_id,
        provider_metadata={
            "workflow_status": result.status.value,
            "intent": result.intent,
            "language": result.language_code,
            "trace_id": str(result.trace_id) if result.trace_id else None,
            "is_mock": True,
            "provider": "workflow-heuristic",
        },
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    return ChatMessageResponse(
        request_id=request_id,
        conversation_id=conversation.id,
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
        provider=_provider_meta(result.language_code),
        workflow=_workflow_out(result),
    )


async def confirm_or_deny_action(
    *,
    db: AsyncSession,
    user: User,
    payload: ConfirmActionRequest,
    request_id: str,
    idempotency_key: str | None = None,
) -> ConfirmActionResponse:
    confirmation = await consume_confirmation(token=payload.confirmation_token, user_id=user.id)

    if not payload.approved:
        assistant_text = respond(language_code=confirmation.language_code, kind="denied")
        conversation = await db.get(Conversation, confirmation.conversation_id)
        if conversation is None or conversation.user_id != user.id:
            raise AppError(
                code="conversation_forbidden",
                message="Conversation not found for confirmation.",
                status_code=403,
            )
        assistant_message = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=assistant_text,
            request_id=request_id,
            provider_metadata={"workflow_status": "denied", "is_mock": True},
        )
        db.add(assistant_message)
        conversation.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(assistant_message)
        workflow = WorkflowOut(
            status=WorkflowStatus.COMPLETED.value,
            detected_language=confirmation.language_code,
            selected_tool=confirmation.tool_name,
            confirmation_required=False,
            tool_execution_status="skipped",
        )
        return ConfirmActionResponse(
            request_id=request_id,
            conversation_id=conversation.id,
            assistant_message=MessageOut.model_validate(assistant_message),
            provider=_provider_meta(confirmation.language_code),
            workflow=workflow,
        )

    language = LanguageResult(
        language_code=confirmation.language_code,
        script="unknown",
        confidence=1.0,
        signals=["confirmation"],
    )
    intent_map = {
        "cancel_order": Intent.CANCEL_ORDER,
        "update_delivery_address": Intent.UPDATE_DELIVERY_ADDRESS,
    }
    intent = intent_map.get(confirmation.tool_name, Intent.UNKNOWN)
    intent_result = IntentResult(intent=intent, confidence=1.0, entities=confirmation.arguments)

    key = idempotency_key or confirmation.idempotency_key
    if not key:
        key = f"confirm:{confirmation.tool_name}:{confirmation.argument_hash}"

    if argument_hash(confirmation.arguments) != confirmation.argument_hash:
        raise AppError(
            code="confirmation_argument_mismatch",
            message="Confirmation arguments do not match the token binding.",
            status_code=400,
        )

    result = await execute_tool_and_respond(
        db=db,
        user=user,
        conversation_id=confirmation.conversation_id,
        message_id=None,
        request_id=request_id,
        language_code=confirmation.language_code,
        script=language.script,
        intent_result=intent_result,
        entities=confirmation.arguments,
        tool_name=confirmation.tool_name,
        args=confirmation.arguments,
        idempotency_key=key,
        started=time.perf_counter(),
        language=language,
    )

    conversation = await db.get(Conversation, confirmation.conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise AppError(
            code="conversation_forbidden",
            message="Conversation not found for confirmation.",
            status_code=403,
        )
    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result.assistant_text,
        request_id=request_id,
        provider_metadata={
            "workflow_status": result.status.value,
            "trace_id": str(result.trace_id) if result.trace_id else None,
            "is_mock": True,
        },
    )
    db.add(assistant_message)
    conversation.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(assistant_message)

    return ConfirmActionResponse(
        request_id=request_id,
        conversation_id=conversation.id,
        assistant_message=MessageOut.model_validate(assistant_message),
        provider=_provider_meta(result.language_code),
        workflow=_workflow_out(result),
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
