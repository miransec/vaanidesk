"""Shared helpers for VaaniDesk backend tests."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import delete, func, or_, select

TEST_KNOWLEDGE_TITLE_PREFIX = "__vdtest__"


async def ensure_order_with_status(demo_key: str, status: str) -> str:
    """Return an order_number for demo_key with the given status.

    If none exists, re-arm an existing owned order (preserves VD-* contiguity).
    """
    from app.database.session import SessionLocal
    from app.models import Order, OrderStatus, User

    wanted = OrderStatus(status)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.demo_key == demo_key))).scalar_one()
        order = (
            await db.execute(
                select(Order).where(Order.user_id == user.id, Order.status == wanted).limit(1)
            )
        ).scalar_one_or_none()
        if order is None:
            order = (
                await db.execute(select(Order).where(Order.user_id == user.id).limit(1))
            ).scalar_one_or_none()
            if order is None:
                raise AssertionError(f"No seeded orders for {demo_key}")
            order.status = wanted
            await db.commit()
            await db.refresh(order)
        return order.order_number


async def ensure_cancellable_order(demo_key: str) -> str:
    """Return a pending/confirmed order ref; re-arm if prior tests cancelled all."""
    from app.database.session import SessionLocal
    from app.models import Order, OrderStatus, User

    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.demo_key == demo_key))).scalar_one()
        order = (
            await db.execute(
                select(Order)
                .where(
                    Order.user_id == user.id,
                    Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED]),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if order is None:
            order = (
                await db.execute(select(Order).where(Order.user_id == user.id).limit(1))
            ).scalar_one_or_none()
            if order is None:
                raise AssertionError(f"No seeded orders for {demo_key}")
            order.status = OrderStatus.PENDING
            await db.commit()
            await db.refresh(order)
        return order.order_number


async def knowledge_counts() -> dict[str, int]:
    from app.database.session import SessionLocal
    from app.models import KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentVersion

    async with SessionLocal() as db:
        docs = (await db.execute(select(func.count()).select_from(KnowledgeDocument))).scalar_one()
        versions = (
            await db.execute(select(func.count()).select_from(KnowledgeDocumentVersion))
        ).scalar_one()
        chunks = (await db.execute(select(func.count()).select_from(KnowledgeChunk))).scalar_one()
    return {"documents": int(docs), "versions": int(versions), "chunks": int(chunks)}


async def delete_test_knowledge_documents() -> int:
    """Remove documents created by Phase 3 tests. Returns deleted count."""
    from app.database.session import SessionLocal
    from app.models import KnowledgeDocument, RetrievalTrace

    async with SessionLocal() as db:
        ids = list(
            (
                await db.execute(
                    select(KnowledgeDocument.id).where(
                        or_(
                            KnowledgeDocument.title.startswith(TEST_KNOWLEDGE_TITLE_PREFIX),
                            KnowledgeDocument.title.like("Test Policy %"),
                            KnowledgeDocument.title.like("Versioned Policy %"),
                            KnowledgeDocument.title.like("ActiveFilter %"),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        count = len(ids)
        if ids:
            # Bulk SQL delete — ORM cascade via relationship can null FKs incorrectly.
            await db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.id.in_(ids)))
        await db.execute(delete(RetrievalTrace).where(RetrievalTrace.request_id.like("test-%")))
        await db.execute(delete(RetrievalTrace).where(RetrievalTrace.request_id.like("iso-%")))
        await db.commit()
    return count


def test_title(label: str) -> str:
    return f"{TEST_KNOWLEDGE_TITLE_PREFIX}{label} {uuid4().hex[:8]}"


TEST_VOICE_REQUEST_PREFIX = "vdtest-voice-"


async def delete_test_voice_artifacts(
    *,
    voice_message_ids: list | None = None,
    request_id_prefix: str = TEST_VOICE_REQUEST_PREFIX,
) -> int:
    """Remove voice rows created by Phase 4 tests. Returns deleted voice message count."""
    from uuid import UUID

    from app.database.session import SessionLocal
    from app.models import SpeechSynthesis, VoiceMessage, VoiceTrace

    removed = 0
    async with SessionLocal() as db:
        if voice_message_ids:
            ids = [UUID(str(v)) for v in voice_message_ids]
            await db.execute(delete(VoiceTrace).where(VoiceTrace.voice_message_id.in_(ids)))
            await db.execute(
                delete(SpeechSynthesis).where(
                    SpeechSynthesis.message_id.in_(
                        select(VoiceMessage.message_id).where(VoiceMessage.id.in_(ids))
                    )
                )
            )
            result = await db.execute(delete(VoiceMessage).where(VoiceMessage.id.in_(ids)))
            removed = result.rowcount or 0
        await db.execute(
            delete(VoiceTrace).where(VoiceTrace.request_id.like(f"{request_id_prefix}%"))
        )
        await db.commit()
    return removed
