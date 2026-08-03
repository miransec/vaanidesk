from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import UUID

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
        pytest.skip("PostgreSQL is not available — start Docker Compose or local Postgres")
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


async def _owned_order_ref(demo_key: str, preferred_status: str | None = None) -> str:
    from app.database.session import SessionLocal
    from app.models import Order, User

    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.demo_key == demo_key))).scalar_one()
        stmt = select(Order).where(Order.user_id == user.id)
        if preferred_status:
            from app.models import OrderStatus

            stmt = stmt.where(Order.status == OrderStatus(preferred_status))
        order = (await db.execute(stmt.limit(1))).scalar_one()
        return order.order_number


@pytest.mark.asyncio
async def test_ready_with_db(client: AsyncClient) -> None:
    res = await client.get("/ready")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert any(c["name"] == "postgresql" and c["status"] == "ok" for c in body["checks"])


@pytest.mark.asyncio
async def test_chat_round_trip_and_persistence(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/chat/messages",
        json={"content": "hello"},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["provider"]["is_mock"] is True
    assert "request_id" in body
    assert body["workflow"]["intent"] == "greeting"
    conversation_id = body["conversation_id"]

    listed = await client.get(
        "/api/v1/conversations",
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert listed.status_code == 200
    assert any(item["id"] == conversation_id for item in listed.json())

    detail = await client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert len(messages) >= 2
    assert messages[-2]["role"] == "user"
    assert messages[-1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_cross_user_conversation_denied(client: AsyncClient) -> None:
    created = await client.post(
        "/api/v1/chat/messages",
        json={"content": "namaste"},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation_id"]

    denied = await client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "conversation_forbidden"


@pytest.mark.asyncio
async def test_hinglish_clarification_via_api(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/chat/messages",
        json={"content": "mera order kahan hai"},
        headers={"X-Demo-User-Key": "demo-priya"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["provider"]["language_hint"] == "hinglish"
    assert body["workflow"]["clarification_required"] is True
    assert body["workflow"]["intent"] == "order_status"


@pytest.mark.asyncio
async def test_seed_idempotent(require_db: None) -> None:
    from scripts.seed import seed

    first = await seed()
    second = await seed()
    assert first["users"] >= 4
    assert first["products"] >= 25
    assert first["orders"] >= 50
    assert second["users"] == first["users"]
    assert second["products"] == first["products"]
    assert second["orders"] == first["orders"]


@pytest.mark.asyncio
async def test_invalid_demo_user(client: AsyncClient) -> None:
    res = await client.post(
        "/api/v1/chat/messages",
        json={"content": "hello"},
        headers={"X-Demo-User-Id": str(UUID("99999999-9999-9999-9999-999999999999"))},
    )
    assert res.status_code == 401
