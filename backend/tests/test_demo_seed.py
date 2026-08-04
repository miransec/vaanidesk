"""Deterministic curated demo seed + product demo-user isolation."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
from app.core.demo_personas import (
    CURATED_DEMO_ORDERS,
    PRODUCT_DEMO_KEYS,
    PRODUCT_DEMO_PERSONAS,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, text
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


def test_aarav_keeps_historical_demo_anya_key() -> None:
    aarav = next(p for p in PRODUCT_DEMO_PERSONAS if p["display_name"] == "Aarav Sharma")
    assert aarav["demo_key"] == "demo-anya"
    assert "demo-aarav" not in PRODUCT_DEMO_KEYS


async def _dispose_global_engine() -> None:
    """Drop pooled asyncpg connections bound to a closed Windows event loop."""
    import contextlib

    from app.database.session import get_engine, reset_engine

    with contextlib.suppress(Exception):
        await get_engine().dispose()
    reset_engine()


@pytest.mark.asyncio
async def test_seed_curated_orders_idempotent(require_db: None) -> None:
    import sys
    from pathlib import Path

    from app.database.session import SessionLocal
    from app.models import Order, User

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from scripts.seed import seed

    try:
        first = await seed(force=False)
        second = await seed(force=False)
        assert "curated_orders" in first
        assert first["curated_orders"] == second["curated_orders"]
        assert second["curated_orders_created"] == 0

        async with SessionLocal() as db:
            for spec in CURATED_DEMO_ORDERS:
                user = (
                    await db.execute(select(User).where(User.demo_key == spec["demo_key"]))
                ).scalar_one()
                order = (
                    await db.execute(
                        select(Order).where(Order.order_number == spec["order_number"])
                    )
                ).scalar_one()
                assert order.user_id == user.id
                assert order.status.value == spec["status"]

            # Exactly one row per curated order number
            for spec in CURATED_DEMO_ORDERS:
                n = (
                    await db.execute(
                        select(func.count())
                        .select_from(Order)
                        .where(Order.order_number == spec["order_number"])
                    )
                ).scalar_one()
                assert n == 1
    finally:
        await _dispose_global_engine()


@pytest.mark.asyncio
async def test_product_demo_matrix_scenarios(require_db: None) -> None:
    import sys
    from pathlib import Path

    from app.database.session import SessionLocal
    from app.models import Order, OrderStatus, User

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from scripts.seed import seed

    try:
        await seed(force=False)

        async with SessionLocal() as db:
            aarav = (
                await db.execute(select(User).where(User.demo_key == "demo-anya"))
            ).scalar_one()
            rahul = (
                await db.execute(select(User).where(User.demo_key == "demo-rahul"))
            ).scalar_one()
            meera = (
                await db.execute(select(User).where(User.demo_key == "demo-meera"))
            ).scalar_one()

            assert aarav.display_name == "Aarav Sharma"
            assert rahul.display_name == "Rahul Verma"
            assert meera.display_name == "Meera Patel"

            aarav_orders = (
                (await db.execute(select(Order).where(Order.user_id == aarav.id))).scalars().all()
            )
            statuses = {o.order_number: o.status for o in aarav_orders}
            assert statuses.get("VD-10021") == OrderStatus.SHIPPED
            assert statuses.get("VD-10022") == OrderStatus.PENDING
            assert statuses.get("VD-10023") == OrderStatus.DELIVERED

            rahul_order = (
                await db.execute(select(Order).where(Order.order_number == "VD-10031"))
            ).scalar_one()
            assert rahul_order.user_id == rahul.id

            meera_order = (
                await db.execute(select(Order).where(Order.order_number == "VD-10041"))
            ).scalar_one()
            assert meera_order.user_id == meera.id
            assert meera_order.status == OrderStatus.DELIVERED
    finally:
        await _dispose_global_engine()


@pytest.mark.asyncio
async def test_demo_users_api_excludes_auth_fixtures(client: AsyncClient) -> None:
    res = await client.get("/api/v1/demo-users")
    assert res.status_code == 200
    rows = res.json()
    keys = {r["demo_key"] for r in rows}
    names = {r["display_name"] for r in rows}
    assert keys == set(PRODUCT_DEMO_KEYS)
    assert names == {p["display_name"] for p in PRODUCT_DEMO_PERSONAS}
    for bad in ("Dup User", "Pw User", "Sess User", "Brute User", "Refresh User"):
        assert bad not in names
