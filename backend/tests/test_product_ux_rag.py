"""Product demo persona isolation + damaged-product RAG regressions."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from app.core.demo_personas import PRODUCT_DEMO_KEYS, PRODUCT_DEMO_PERSONAS
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

FORBIDDEN_DEMO_NAMES = (
    "Dup User",
    "Pw User",
    "Sess User",
    "Brute User",
    "Refresh User",
    "Test User",
    "Login User",
    "Logout User",
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


@pytest.fixture
async def ensure_corpus(require_db: None) -> None:
    import sys
    from pathlib import Path

    from app.database.session import SessionLocal
    from app.models import KnowledgeChunk, KnowledgeDocument

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from scripts.seed_knowledge import seed_knowledge

    async with SessionLocal() as db:
        docs = (await db.execute(select(func.count()).select_from(KnowledgeDocument))).scalar_one()
        chunks = (await db.execute(select(func.count()).select_from(KnowledgeChunk))).scalar_one()
    if int(docs) < 12 or int(chunks) < 100:
        await seed_knowledge(force=False)


def test_seed_personas_exclude_auth_fixture_names() -> None:
    from app.core.demo_personas import TEST_COMPAT_PERSONAS

    all_names = [p["display_name"] for p in [*PRODUCT_DEMO_PERSONAS, *TEST_COMPAT_PERSONAS]]
    for bad in FORBIDDEN_DEMO_NAMES:
        assert bad not in all_names


@pytest.mark.asyncio
async def test_demo_users_api_returns_only_product_personas(client: AsyncClient) -> None:
    res = await client.get("/api/v1/demo-users")
    assert res.status_code == 200
    rows = res.json()
    keys = {r["demo_key"] for r in rows}
    names = {r["display_name"] for r in rows}
    assert keys == set(PRODUCT_DEMO_KEYS)
    assert names == {p["display_name"] for p in PRODUCT_DEMO_PERSONAS}
    for bad in FORBIDDEN_DEMO_NAMES:
        assert bad not in names
    assert all("@" in r["email"] for r in rows)


CUSTOMER_POLICY_QUERIES = [
    "What is the refund policy for a damaged product?",
    "Can I get a refund if my item arrived damaged?",
    "My product is defective. Can I return it?",
    "Damaged item ke liye refund milega?",
    "Mera product damaged aaya hai, replacement ya refund mil sakta hai?",
]


@pytest.mark.asyncio
async def test_damaged_product_policy_prefers_customer_authority(
    client: AsyncClient, ensure_corpus: None
) -> None:
    for content in CUSTOMER_POLICY_QUERIES:
        res = await client.post(
            "/api/v1/chat/messages",
            headers={"X-Demo-User-Key": "demo-anya", "Idempotency-Key": f"dmg-{uuid4()}"},
            json={"content": content},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        wf = body["workflow"]
        assert wf["intent"] == "policy_question"
        assert "evidence_confidence_band" in wf
        if wf.get("no_answer"):
            lower = body["assistant_message"]["content"].lower()
            assert "reliable" in lower or "confident" in lower
            continue
        titles = " ".join(c["document_title"].lower() for c in wf.get("citations") or [])
        assert "damaged" in titles or "return" in titles or "refund" in titles
        primary = (wf.get("citations") or [{}])[0].get("document_title", "").lower()
        assert "escalation" not in primary
        assert "de-escalation" not in primary
        assert "safety hub" not in primary
        assert "product instructions" not in primary


@pytest.mark.asyncio
async def test_agent_coaching_query_may_use_deescalation(
    client: AsyncClient, ensure_corpus: None
) -> None:
    res = await client.post(
        "/api/v1/chat/messages",
        headers={"X-Demo-User-Key": "demo-anya", "Idempotency-Key": f"agent-{uuid4()}"},
        json={
            "content": ("What should an agent say when a customer is angry about a damaged item?")
        },
    )
    assert res.status_code == 200, res.text
    wf = res.json()["workflow"]
    assert wf["intent"] == "policy_question"
    if wf.get("no_answer"):
        return
    titles = " ".join(c["document_title"].lower() for c in wf.get("citations") or [])
    assert (
        "de-escalation" in titles
        or "escalation" in titles
        or "damaged" in titles
        or "agent" in titles
        or "playbook" in titles
    )


@pytest.mark.asyncio
async def test_damaged_retrieval_trace_ranks_damaged_policy(
    client: AsyncClient, ensure_corpus: None
) -> None:
    res = await client.post(
        "/api/v1/knowledge/retrieval/test",
        headers={"X-Demo-User-Key": "demo-anya"},
        json={
            "query": "What is the refund policy for a damaged product?",
            "strategy": "hybrid",
            "persist_trace": True,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data.get("confidence") is not None
    if data.get("no_answer"):
        pytest.skip("corpus abstained — confidence gate held")
    cites = data.get("citations") or []
    assert cites
    top = cites[0]["document_title"].lower()
    assert "damaged" in top
    assert "escalation guide" not in top
    assert "de-escalation" not in top
