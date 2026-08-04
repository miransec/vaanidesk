from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://vaanidesk:vaanidesk_dev_password@localhost:5432/vaanidesk",
)

pytestmark = pytest.mark.skipif(
    os.getenv("VAANIDESK_SKIP_DB_TESTS", "").lower() in {"1", "true", "yes"},
    reason="VAANIDESK_SKIP_DB_TESTS set",
)


async def _db_available() -> bool:
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture
async def require_db() -> AsyncIterator[None]:
    if not await _db_available():
        pytest.skip("PostgreSQL is not available")
    yield


@pytest.fixture
async def client(require_db: None) -> AsyncIterator[AsyncClient]:
    os.environ["DATABASE_URL"] = DATABASE_URL
    os.environ["LLM_PROVIDER"] = "mock"
    from app.core.config import get_settings
    from app.core.redis import reset_redis
    from app.database.session import get_db, reset_engine
    from app.main import create_app

    get_settings.cache_clear()
    reset_engine()
    await reset_redis()
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    app = create_app()

    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await reset_redis()
    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()


async def _order_for(demo_key: str, status: str | None = None) -> str:
    from tests.helpers import ensure_order_with_status

    if status:
        return await ensure_order_with_status(demo_key, status)

    from app.database.session import SessionLocal
    from app.models import Order, User

    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.demo_key == demo_key))).scalar_one()
        order = (
            await db.execute(select(Order).where(Order.user_id == user.id).limit(1))
        ).scalar_one_or_none()
        if order is None:
            raise AssertionError(f"No seeded orders for {demo_key}")
        return order.order_number


async def _delivered_owned() -> tuple[str, str]:
    from app.database.session import SessionLocal
    from app.models import Order, OrderStatus, User

    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(Order, User)
                .join(User, User.id == Order.user_id)
                .where(Order.status == OrderStatus.DELIVERED)
                .limit(1)
            )
        ).first()
        if row is None:
            # Re-arm one order to delivered for the cross-user denial fixture
            any_row = (
                await db.execute(select(Order, User).join(User, User.id == Order.user_id).limit(1))
            ).first()
            if any_row is None:
                raise AssertionError("No seeded orders available")
            order, user = any_row
            order.status = OrderStatus.DELIVERED
            await db.commit()
            return user.demo_key, order.order_number
        order, user = row
        return user.demo_key, order.order_number


@pytest.mark.asyncio
async def test_english_order_status(client: AsyncClient) -> None:
    ref = await _order_for("demo-anya")
    res = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"where is my order {ref}"},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["workflow"]["intent"] == "order_status"
    assert body["workflow"]["selected_tool"] == "get_order_status"
    assert body["workflow"]["tool_execution_status"] == "success"
    assert ref in body["assistant_message"]["content"]
    assert body["workflow"]["trace_id"]


@pytest.mark.asyncio
async def test_multilingual_order_status(client: AsyncClient) -> None:
    ref = await _order_for("demo-anya")
    cases = [
        (f"mera order {ref} kidhar hai", "hinglish"),
        (f"मेरा ऑर्डर {ref} कहाँ है", "hi"),
        (f"माझी ऑर्डर {ref} कुठे आहे", "mr"),
    ]
    for content, lang in cases:
        res = await client.post(
            "/api/v1/chat/messages",
            json={"content": content},
            headers={"X-Demo-User-Key": "demo-anya"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["workflow"]["detected_language"] == lang
        assert body["workflow"]["selected_tool"] == "get_order_status"


@pytest.mark.asyncio
async def test_cross_user_order_denied(client: AsyncClient) -> None:
    ref = await _order_for("demo-anya")
    res = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"where is my order {ref}"},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["workflow"]["status"] == "failed"
    assert body["workflow"]["tool_execution_status"] == "failed"


@pytest.mark.asyncio
async def test_cancel_confirmation_approve_and_idempotent(client: AsyncClient) -> None:
    ref = await _order_for("demo-anya", status="pending")
    # If no pending, try confirmed
    try:
        ref = await _order_for("demo-anya", status="pending")
    except Exception:
        ref = await _order_for("demo-anya", status="confirmed")

    first = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["workflow"]["confirmation_required"] is True
    token = body["workflow"]["confirmation"]["token"]
    assert "cancel order" in body["workflow"]["confirmation"]["summary"].lower()

    # Other user cannot confirm
    denied = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token, "approved": True},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert denied.status_code == 403

    # Owner approves
    key = f"test-cancel-{uuid4()}"
    approved = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token, "approved": True},
        headers={"X-Demo-User-Key": "demo-anya", "Idempotency-Key": key},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["workflow"]["tool_execution_status"] == "success"

    # Reused token rejected
    reused = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token, "approved": True},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert reused.status_code == 400

    # Second cancel attempt on already cancelled → eligibility fail or confirmation then fail
    again = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert again.status_code == 200
    # May require confirmation then fail on execute, or fail if we checked eligibility earlier.
    # High-risk still asks confirmation first.
    assert again.json()["workflow"]["confirmation_required"] is True
    token2 = again.json()["workflow"]["confirmation"]["token"]
    fail_exec = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token2, "approved": True},
        headers={"X-Demo-User-Key": "demo-anya", "Idempotency-Key": f"test-cancel2-{uuid4()}"},
    )
    assert fail_exec.status_code == 200
    assert fail_exec.json()["workflow"]["status"] == "failed"


@pytest.mark.asyncio
async def test_cancel_denied(client: AsyncClient) -> None:
    ref = await _order_for("demo-rahul", status="confirmed")
    first = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert first.status_code == 200
    token = first.json()["workflow"]["confirmation"]["token"]
    denied = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token, "approved": False},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert denied.status_code == 200
    assert denied.json()["workflow"]["tool_execution_status"] == "skipped"


@pytest.mark.asyncio
async def test_address_confirmation(client: AsyncClient) -> None:
    ref = await _order_for("demo-priya", status="pending")
    res = await client.post(
        "/api/v1/chat/messages",
        json={
            "content": (
                f"change delivery address for {ref} to 42 Marine Drive Apartment 5 Mumbai 400020"
            )
        },
        headers={"X-Demo-User-Key": "demo-priya"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["workflow"]["selected_tool"] == "update_delivery_address"
    assert body["workflow"]["confirmation_required"] is True


@pytest.mark.asyncio
async def test_escalation_unknown(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/chat/messages",
        json={"content": "zzzz unrelated gibberish 999"},
        headers={"X-Demo-User-Key": "demo-arjun"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["workflow"]["escalation_required"] is True
    assert body["workflow"]["selected_tool"] == "transfer_to_human"


@pytest.mark.asyncio
async def test_ticket_create_idempotent(client: AsyncClient) -> None:
    key = f"ticket-{uuid4()}"
    payload = {"content": "create a support ticket about delayed packaging foam smell"}
    first = await client.post(
        "/api/v1/chat/messages",
        json=payload,
        headers={"X-Demo-User-Key": "demo-anya", "Idempotency-Key": key},
    )
    assert first.status_code == 200, first.text
    assert first.json()["workflow"]["selected_tool"] == "create_support_ticket"
    ref = None
    # Extract TKT from message
    import re

    m = re.search(r"TKT-\d+", first.json()["assistant_message"]["content"])
    assert m
    ref = m.group(0)

    second = await client.post(
        "/api/v1/chat/messages",
        json=payload,
        headers={"X-Demo-User-Key": "demo-anya", "Idempotency-Key": key},
    )
    assert second.status_code == 200
    assert ref in second.json()["assistant_message"]["content"]


@pytest.mark.asyncio
async def test_delivered_order_cannot_cancel(client: AsyncClient) -> None:
    demo_key, ref = await _delivered_owned()
    first = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": demo_key},
    )
    assert first.status_code == 200
    assert first.json()["workflow"]["confirmation_required"] is True
    token = first.json()["workflow"]["confirmation"]["token"]
    result = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token, "approved": True},
        headers={"X-Demo-User-Key": demo_key, "Idempotency-Key": f"del-{uuid4()}"},
    )
    assert result.status_code == 200
    assert result.json()["workflow"]["status"] == "failed"


@pytest.mark.asyncio
async def test_tool_layer_authz_direct(require_db: None) -> None:
    from app.core.errors import AppError
    from app.database.session import SessionLocal
    from app.models import User
    from app.tools.orders import OrderRefInput, handle_get_order_status

    async with SessionLocal() as db:
        anya = (await db.execute(select(User).where(User.demo_key == "demo-anya"))).scalar_one()
        rahul = (await db.execute(select(User).where(User.demo_key == "demo-rahul"))).scalar_one()
        ref = await _order_for("demo-anya")
        ok = await handle_get_order_status(db=db, user=anya, args=OrderRefInput(order_ref=ref))
        assert ok["order_ref"] == ref
        with pytest.raises(AppError) as exc:
            await handle_get_order_status(db=db, user=rahul, args=OrderRefInput(order_ref=ref))
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_invalid_confirmation_token(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": "x" * 40, "approved": True},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert res.status_code == 400
