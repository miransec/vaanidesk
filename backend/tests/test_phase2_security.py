"""Phase 2 security & reproducibility verification suite.

Does not weaken existing tests — adds coverage for migration stability,
confirmation token handling, Redis fail-closed, idempotency/concurrency,
direct tool AuthZ, and sensitive logging inspection.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
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
    from app.core.config import get_settings
    from app.core.redis import reset_redis
    from app.database.session import reset_engine

    get_settings.cache_clear()
    reset_engine()
    await reset_redis()
    yield
    await reset_redis()
    reset_engine()
    get_settings.cache_clear()


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


async def _cancellable_order(demo_key: str = "demo-anya") -> str:
    from tests.helpers import ensure_cancellable_order

    return await ensure_cancellable_order(demo_key)


# ---------------------------------------------------------------------------
# Order reference stability
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_order_refs_unique_and_vd_format(require_db: None) -> None:
    from app.database.session import SessionLocal
    from app.models import Order

    async with SessionLocal() as db:
        refs = list((await db.execute(select(Order.order_number))).scalars().all())
    assert refs
    assert len(refs) == len(set(refs))
    assert all(r.startswith("VD-") for r in refs)
    # Deterministic contiguous mapping from seed/migration formula
    nums = sorted(int(r.removeprefix("VD-")) for r in refs)
    assert nums[0] == 10001
    assert nums == list(range(nums[0], nums[0] + len(nums)))


@pytest.mark.asyncio
async def test_order_ref_mapping_independent_of_row_order(require_db: None) -> None:
    """Public refs must be a pure function of the numeric identity, not SELECT order."""
    from app.database.session import SessionLocal

    async with SessionLocal() as db:
        # Simulate the migration formula both ASC and DESC — results must match per number.
        rows_asc = (
            await db.execute(
                text(
                    """
                    SELECT order_number,
                           'VD-' || (10001 + (
                             CASE WHEN order_number ~ '^[0-9]+$'
                               THEN order_number::integer
                               ELSE REPLACE(order_number, 'VD-', '')::integer
                                    - 10001 + 8300
                             END - 8300
                           ))::text AS projected
                    FROM orders
                    ORDER BY order_number ASC
                    """
                )
            )
        ).all()
        rows_desc = (
            await db.execute(
                text(
                    """
                    SELECT order_number,
                           'VD-' || (10001 + (
                             CASE WHEN order_number ~ '^[0-9]+$'
                               THEN order_number::integer
                               ELSE REPLACE(order_number, 'VD-', '')::integer
                                    - 10001 + 8300
                             END - 8300
                           ))::text AS projected
                    FROM orders
                    ORDER BY order_number DESC
                    """
                )
            )
        ).all()
    map_asc = {r[0]: r[1] for r in rows_asc}
    map_desc = {r[0]: r[1] for r in rows_desc}
    assert map_asc == map_desc
    # Already-VD refs project to themselves
    for current, projected in map_asc.items():
        if current.startswith("VD-"):
            assert current == projected


# ---------------------------------------------------------------------------
# Confirmation token design
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirmation_token_hashed_at_rest_and_bound(require_db: None) -> None:
    from uuid import UUID

    from app.core.redis import get_redis, reset_redis
    from app.security.confirmation import create_confirmation, token_storage_key
    from app.security.redaction import argument_hash

    await reset_redis()
    user_id = UUID("11111111-1111-1111-1111-111111111111")
    conv_id = uuid4()
    args = {"order_ref": "VD-10001"}
    payload = await create_confirmation(
        user_id=user_id,
        tool_name="cancel_order",
        arguments=args,
        conversation_id=conv_id,
        request_id="req-verify",
        summary="Cancel order VD-10001",
        language_code="en",
    )
    client = await get_redis()
    # Raw token must NOT be a Redis key prefix value
    assert await client.get(f"vd:confirm:{payload.token}") is None
    stored = await client.get(token_storage_key(payload.token))
    assert stored is not None
    data = json.loads(stored)
    assert "token" not in data
    assert payload.token not in stored
    assert data["user_id"] == str(user_id)
    assert data["tool_name"] == "cancel_order"
    assert data["argument_hash"] == argument_hash(args)
    assert data["arguments"]["order_ref"] == "VD-10001"
    await client.delete(token_storage_key(payload.token))


@pytest.mark.asyncio
async def test_confirmation_expired_and_single_use(client: AsyncClient) -> None:
    from app.core.redis import get_redis
    from app.security.confirmation import token_storage_key

    ref = await _cancellable_order("demo-rahul")
    first = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert first.status_code == 200
    token = first.json()["workflow"]["confirmation"]["token"]

    # Force expiry in Redis payload
    redis = await get_redis()
    key = token_storage_key(token)
    raw = await redis.get(key)
    assert raw
    data = json.loads(raw)
    data["expires_at"] = (datetime.now(UTC) - timedelta(seconds=5)).isoformat()
    await redis.set(key, json.dumps(data), ex=60)

    expired = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token, "approved": True},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "confirmation_expired"

    # Fresh token → approve once → reuse fails
    again = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    token2 = again.json()["workflow"]["confirmation"]["token"]
    ok = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token2, "approved": False},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert ok.status_code == 200
    reused = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token2, "approved": True},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert reused.status_code == 400


@pytest.mark.asyncio
async def test_confirmation_not_logged(caplog: pytest.LogCaptureFixture, require_db: None) -> None:
    from app.security.confirmation import create_confirmation, deny_confirmation

    caplog.set_level(logging.DEBUG)
    user_id = __import__("uuid").UUID("11111111-1111-1111-1111-111111111111")
    payload = await create_confirmation(
        user_id=user_id,
        tool_name="cancel_order",
        arguments={"order_ref": "VD-10999"},
        conversation_id=uuid4(),
        request_id="log-check",
        summary="Cancel order VD-10999",
        language_code="en",
    )
    await deny_confirmation(token=payload.token, user_id=user_id)
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert payload.token not in joined


# ---------------------------------------------------------------------------
# Redis fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_redis_fail_closed_cancel_create_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.database.session import SessionLocal
    from app.models import Order, OrderStatus

    ref = await _cancellable_order("demo-priya")

    async def _boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.security.confirmation.get_redis", _boom)
    monkeypatch.setattr("app.core.redis.get_redis", _boom)

    before_status = None
    async with SessionLocal() as db:
        order = (await db.execute(select(Order).where(Order.order_number == ref))).scalar_one()
        before_status = order.status

    res = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": "demo-priya"},
    )
    assert res.status_code == 503, res.text
    assert res.json()["error"]["code"] == "confirmation_unavailable"

    async with SessionLocal() as db:
        order = (await db.execute(select(Order).where(Order.order_number == ref))).scalar_one()
        assert order.status == before_status
        assert order.status != OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_redis_fail_closed_confirm_execute_returns_503(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = await _cancellable_order("demo-arjun")
    first = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": "demo-arjun"},
    )
    assert first.status_code == 200
    token = first.json()["workflow"]["confirmation"]["token"]

    async def _boom():
        raise ConnectionError("redis down")

    monkeypatch.setattr("app.security.confirmation.get_redis", _boom)

    res = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token, "approved": True},
        headers={"X-Demo-User-Key": "demo-arjun"},
    )
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "confirmation_unavailable"


# ---------------------------------------------------------------------------
# Idempotency + concurrency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotent_cancel_exactly_once(client: AsyncClient) -> None:
    from app.database.session import SessionLocal
    from app.models import Order, OrderStatus

    ref = await _cancellable_order("demo-anya")
    key = f"cancel-once-{uuid4()}"
    first = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    token = first.json()["workflow"]["confirmation"]["token"]
    a = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token, "approved": True},
        headers={"X-Demo-User-Key": "demo-anya", "Idempotency-Key": key},
    )
    assert a.status_code == 200
    assert a.json()["workflow"]["tool_execution_status"] == "success"

    # Second chat+confirm path with same idempotency key after already cancelled:
    # Direct idempotency replay via begin_or_replay
    from app.models import User
    from app.security.idempotency import begin_or_replay

    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.demo_key == "demo-anya"))).scalar_one()
        record, replay = await begin_or_replay(
            db=db,
            user_id=user.id,
            tool_name="cancel_order",
            arguments={"order_ref": ref},
            idempotency_key=key,
        )
        assert record is None
        assert replay is not None
        assert replay.get("cancelled") is True
        order = (await db.execute(select(Order).where(Order.order_number == ref))).scalar_one()
        assert order.status == OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_idempotency_conflict_and_cross_user(client: AsyncClient, require_db: None) -> None:
    from app.core.errors import AppError
    from app.database.session import SessionLocal
    from app.models import User
    from app.security.idempotency import begin_or_replay, complete_record

    key = f"shared-key-{uuid4()}"
    async with SessionLocal() as db:
        anya = (await db.execute(select(User).where(User.demo_key == "demo-anya"))).scalar_one()
        rahul = (await db.execute(select(User).where(User.demo_key == "demo-rahul"))).scalar_one()
        rec, _ = await begin_or_replay(
            db=db,
            user_id=anya.id,
            tool_name="create_support_ticket",
            arguments={"title": "A", "description": "desc long enough"},
            idempotency_key=key,
        )
        assert rec is not None
        await complete_record(record=rec, result={"ticket_ref": "TKT-TEST"})
        await db.commit()

        with pytest.raises(AppError) as exc:
            await begin_or_replay(
                db=db,
                user_id=anya.id,
                tool_name="create_support_ticket",
                arguments={"title": "B", "description": "different arguments here"},
                idempotency_key=key,
            )
        assert exc.value.status_code == 409

        # Same key, different user → separate record allowed (cannot reuse another's result)
        other, replay = await begin_or_replay(
            db=db,
            user_id=rahul.id,
            tool_name="create_support_ticket",
            arguments={"title": "A", "description": "desc long enough"},
            idempotency_key=key,
        )
        assert replay is None
        assert other is not None
        await db.rollback()


@pytest.mark.asyncio
async def test_concurrent_idempotency_single_winner(require_db: None) -> None:
    from app.core.errors import AppError
    from app.database.session import SessionLocal, get_session_factory
    from app.models import IdempotencyRecord, IdempotencyState, User
    from app.security.idempotency import begin_or_replay, complete_record

    key = f"concurrent-{uuid4()}"
    args = {"title": "Concurrent", "description": "concurrent ticket body text"}

    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.demo_key == "demo-anya"))).scalar_one()
        user_id = user.id

    factory = get_session_factory()

    async def attempt() -> str:
        async with factory() as db:
            try:
                rec, replay = await begin_or_replay(
                    db=db,
                    user_id=user_id,
                    tool_name="create_support_ticket",
                    arguments=args,
                    idempotency_key=key,
                )
                if replay is not None:
                    await db.commit()
                    return "replay"
                assert rec is not None
                await asyncio.sleep(0.05)
                await complete_record(record=rec, result={"ticket_ref": "TKT-CONC", "ok": True})
                await db.commit()
                return "created"
            except AppError as exc:
                await db.rollback()
                if exc.code == "idempotency_in_progress":
                    return "in_progress"
                raise

    results = await asyncio.gather(attempt(), attempt(), attempt())
    assert results.count("created") == 1
    assert results.count("created") + results.count("replay") + results.count("in_progress") == 3

    async with SessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.idempotency_key == key,
                        IdempotencyRecord.user_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].state == IdempotencyState.COMPLETED


# ---------------------------------------------------------------------------
# Direct tool-layer AuthZ (bypass routers)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_direct_tool_authz_order_and_ticket(require_db: None) -> None:
    from uuid import uuid4

    from app.core.config import get_settings
    from app.core.errors import AppError
    from app.database.session import SessionLocal, reset_engine
    from app.models import SupportTicket, TicketCategory, TicketStatus, User
    from app.tools.orders import OrderRefInput, handle_get_order_status
    from app.tools.tickets import TicketRefInput, handle_get_support_ticket_status

    get_settings.cache_clear()
    reset_engine()
    ref = await _cancellable_order("demo-anya")
    async with SessionLocal() as db:
        anya = (await db.execute(select(User).where(User.demo_key == "demo-anya"))).scalar_one()
        rahul = (await db.execute(select(User).where(User.demo_key == "demo-rahul"))).scalar_one()
        ok = await handle_get_order_status(db=db, user=anya, args=OrderRefInput(order_ref=ref))
        assert ok["order_ref"] == ref
        with pytest.raises(AppError) as exc:
            await handle_get_order_status(db=db, user=rahul, args=OrderRefInput(order_ref=ref))
        assert exc.value.status_code == 404
        assert exc.value.code == "order_not_found"

        ticket = SupportTicket(
            id=uuid4(),
            user_id=anya.id,
            public_ticket_ref=f"TKT-{90000 + (hash(str(uuid4())) % 1000)}",
            category=TicketCategory.OTHER,
            title="AuthZ check",
            description="owned by anya only",
            status=TicketStatus.OPEN,
        )
        db.add(ticket)
        await db.flush()
        got = await handle_get_support_ticket_status(
            db=db, user=anya, args=TicketRefInput(ticket_ref=ticket.public_ticket_ref)
        )
        assert got["ticket_ref"] == ticket.public_ticket_ref
        with pytest.raises(AppError) as texc:
            await handle_get_support_ticket_status(
                db=db, user=rahul, args=TicketRefInput(ticket_ref=ticket.public_ticket_ref)
            )
        assert texc.value.status_code == 404
        await db.rollback()


@pytest.mark.asyncio
async def test_public_ref_alone_never_bypasses_ownership(require_db: None) -> None:
    """Knowing VD-* without matching user_id must not return data."""
    from app.core.config import get_settings
    from app.core.errors import AppError
    from app.database.session import SessionLocal, reset_engine
    from app.models import Order, User
    from app.tools.orders import OrderRefInput, get_owned_order, handle_cancel_order

    get_settings.cache_clear()
    reset_engine()
    async with SessionLocal() as db:
        order = (await db.execute(select(Order).limit(1))).scalar_one()
        owner = await db.get(User, order.user_id)
        other = (
            await db.execute(select(User).where(User.id != order.user_id).limit(1))
        ).scalar_one()
        assert owner is not None
        with pytest.raises(AppError):
            await get_owned_order(db=db, user=other, order_ref=order.order_number)
        with pytest.raises(AppError):
            await handle_cancel_order(
                db=db, user=other, args=OrderRefInput(order_ref=order.order_number)
            )


# ---------------------------------------------------------------------------
# Trace / log redaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_traces_redact_tokens_and_truncate_addresses(client: AsyncClient) -> None:
    from app.database.session import SessionLocal
    from app.models import AgentTrace, ToolExecution

    ref = await _cancellable_order("demo-priya")
    long_addr = "42 Marine Drive Wing B Flat 1901 Near Cafe Mondegar Colaba Mumbai 400005 India"
    res = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"change delivery address for {ref} to {long_addr}"},
        headers={"X-Demo-User-Key": "demo-priya"},
    )
    assert res.status_code == 200
    body = res.json()
    token = body["workflow"]["confirmation"]["token"]
    trace_id = body["workflow"]["trace_id"]

    async with SessionLocal() as db:
        trace = await db.get(AgentTrace, __import__("uuid").UUID(trace_id))
        assert trace is not None
        blob = json.dumps(trace.extracted_entities or {})
        assert token not in blob
        assert "password" not in blob.lower()
        te = (
            await db.execute(
                select(ToolExecution).where(ToolExecution.trace_id == trace.id).limit(1)
            )
        ).scalar_one_or_none()
        if te and te.argument_summary:
            summary = json.dumps(te.argument_summary)
            assert token not in summary
            addr = te.argument_summary.get("new_address", "")
            if addr:
                assert addr.endswith("…") or len(addr) <= 40


# ---------------------------------------------------------------------------
# Frontend-facing API contract (approve / deny / expired / reused / unauthorized / redis)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_frontend_confirm_flows_approve_deny_unauthorized(client: AsyncClient) -> None:
    ref = await _cancellable_order("demo-rahul")
    first = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref}"},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert first.status_code == 200
    conf = first.json()["workflow"]["confirmation"]
    assert conf["summary"].startswith("Cancel order")
    assert "token" in conf

    # Unauthorized (other user) — FE would surface error from confirmAction
    denied_user = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": conf["token"], "approved": True},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert denied_user.status_code == 403

    # Owner deny
    denied = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": conf["token"], "approved": False},
        headers={"X-Demo-User-Key": "demo-rahul"},
    )
    assert denied.status_code == 200
    assert denied.json()["workflow"]["tool_execution_status"] == "skipped"

    # Approve path on a fresh cancellable order
    ref2 = await _cancellable_order("demo-anya")
    req = await client.post(
        "/api/v1/chat/messages",
        json={"content": f"please cancel my order {ref2}"},
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    token = req.json()["workflow"]["confirmation"]["token"]
    approved = await client.post(
        "/api/v1/actions/confirm",
        json={"confirmation_token": token, "approved": True},
        headers={"X-Demo-User-Key": "demo-anya", "Idempotency-Key": f"fe-{uuid4()}"},
    )
    assert approved.status_code == 200
    assert approved.json()["workflow"]["tool_execution_status"] == "success"
