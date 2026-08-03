"""Support ticket tools."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import (
    SupportTicket,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    User,
)


class CreateTicketInput(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=8, max_length=4000)
    category: TicketCategory = TicketCategory.OTHER
    priority: TicketPriority = TicketPriority.NORMAL

    @field_validator("title", "description")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned


class TicketRefInput(BaseModel):
    ticket_ref: str = Field(min_length=3, max_length=32)

    @field_validator("ticket_ref")
    @classmethod
    def normalize_ref(cls, value: str) -> str:
        return value.strip().upper()


class TransferHumanInput(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    title: str = Field(default="Human escalation request", max_length=200)

    @field_validator("reason", "title")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


async def _next_ticket_ref(db: AsyncSession) -> str:
    count = (await db.execute(select(func.count()).select_from(SupportTicket))).scalar_one()
    return f"TKT-{10001 + int(count)}"


async def get_owned_ticket(*, db: AsyncSession, user: User, ticket_ref: str) -> SupportTicket:
    stmt = select(SupportTicket).where(
        SupportTicket.user_id == user.id,
        SupportTicket.public_ticket_ref == ticket_ref.upper(),
    )
    ticket = (await db.execute(stmt)).scalar_one_or_none()
    if ticket is None:
        raise AppError(
            code="ticket_not_found",
            message="Support ticket not found for this user.",
            status_code=404,
        )
    return ticket


async def handle_create_support_ticket(
    *,
    db: AsyncSession,
    user: User,
    args: CreateTicketInput,
    conversation_id: UUID | None = None,
    **_: Any,
) -> dict[str, Any]:
    ref = await _next_ticket_ref(db)
    ticket = SupportTicket(
        id=uuid4(),
        user_id=user.id,
        conversation_id=conversation_id,
        public_ticket_ref=ref,
        category=args.category,
        title=args.title,
        description=args.description,
        status=TicketStatus.OPEN,
        priority=args.priority,
    )
    db.add(ticket)
    await db.flush()
    return {
        "ticket_ref": ticket.public_ticket_ref,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "category": ticket.category.value,
        "title": ticket.title,
    }


async def handle_get_support_ticket_status(
    *, db: AsyncSession, user: User, args: TicketRefInput, **_: Any
) -> dict[str, Any]:
    ticket = await get_owned_ticket(db=db, user=user, ticket_ref=args.ticket_ref)
    return {
        "ticket_ref": ticket.public_ticket_ref,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "category": ticket.category.value,
        "title": ticket.title,
        "escalation_reason": ticket.escalation_reason,
    }


async def handle_transfer_to_human(
    *,
    db: AsyncSession,
    user: User,
    args: TransferHumanInput,
    conversation_id: UUID | None = None,
    **_: Any,
) -> dict[str, Any]:
    ref = await _next_ticket_ref(db)
    ticket = SupportTicket(
        id=uuid4(),
        user_id=user.id,
        conversation_id=conversation_id,
        public_ticket_ref=ref,
        category=TicketCategory.HUMAN_ESCALATION,
        title=args.title[:200],
        description=args.reason,
        status=TicketStatus.OPEN,
        priority=TicketPriority.HIGH,
        escalation_reason=args.reason,
    )
    db.add(ticket)
    await db.flush()
    return {
        "ticket_ref": ticket.public_ticket_ref,
        "status": ticket.status.value,
        "queued": True,
        "live_agent_joined": False,
        "message": "Human handoff queued for this portfolio demo — no live agent joined.",
    }
