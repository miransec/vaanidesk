"""Human handoff queue management."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.channels import HandoffStatus, HumanHandoffQueueItem

logger = logging.getLogger(__name__)


async def escalate_to_human(
    *,
    db: AsyncSession,
    conversation_id: UUID,
    summary: str,
) -> HumanHandoffQueueItem:
    """Add conversation to human handoff queue, pausing auto-responses."""
    existing = (
        await db.execute(
            select(HumanHandoffQueueItem).where(
                HumanHandoffQueueItem.conversation_id == conversation_id,
                HumanHandoffQueueItem.status.in_([HandoffStatus.QUEUED, HandoffStatus.ASSIGNED]),
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        return existing

    item = HumanHandoffQueueItem(
        id=uuid4(),
        conversation_id=conversation_id,
        status=HandoffStatus.QUEUED,
        summary=summary[:2000],
    )
    db.add(item)
    await db.flush()
    return item


async def assign_handoff(
    *,
    db: AsyncSession,
    handoff_id: UUID,
    agent_id: str,
) -> HumanHandoffQueueItem:
    """Assign a queued handoff to a human agent."""
    item = await db.get(HumanHandoffQueueItem, handoff_id)
    if item is None:
        raise AppError(code="handoff_not_found", message="Handoff item not found.", status_code=404)

    if item.status not in (HandoffStatus.QUEUED, HandoffStatus.ASSIGNED):
        raise AppError(
            code="handoff_not_assignable",
            message="Handoff is not in assignable state.",
            status_code=400,
        )

    item.status = HandoffStatus.ASSIGNED
    item.assigned_agent_id = agent_id
    await db.flush()
    return item


async def resolve_handoff(
    *,
    db: AsyncSession,
    handoff_id: UUID,
) -> HumanHandoffQueueItem:
    """Mark handoff as resolved."""
    item = await db.get(HumanHandoffQueueItem, handoff_id)
    if item is None:
        raise AppError(code="handoff_not_found", message="Handoff item not found.", status_code=404)

    item.status = HandoffStatus.RESOLVED
    await db.flush()
    return item


async def is_conversation_handed_off(
    *,
    db: AsyncSession,
    conversation_id: UUID,
) -> bool:
    """Check if conversation is currently in handoff (pausing auto-responses)."""
    stmt = select(HumanHandoffQueueItem).where(
        HumanHandoffQueueItem.conversation_id == conversation_id,
        HumanHandoffQueueItem.status.in_([HandoffStatus.QUEUED, HandoffStatus.ASSIGNED]),
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def list_handoff_queue(
    *,
    db: AsyncSession,
    status_filter: HandoffStatus | None = None,
) -> list[HumanHandoffQueueItem]:
    """List handoff queue items."""
    stmt = select(HumanHandoffQueueItem).order_by(HumanHandoffQueueItem.created_at.asc())
    if status_filter:
        stmt = stmt.where(HumanHandoffQueueItem.status == status_filter)
    return list((await db.execute(stmt)).scalars().all())
