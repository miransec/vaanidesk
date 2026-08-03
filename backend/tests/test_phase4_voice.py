"""Phase 4 voice — upload, STT/TTS, transcript gate, security, workflow integration."""

from __future__ import annotations

import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from app.voice.stt import FIXTURE_TRANSCRIPTS
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://vaanidesk:vaanidesk_dev_password@localhost:5432/vaanidesk",
)

AUDIO_DIR = Path(__file__).resolve().parents[2] / "sample_data" / "audio"

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
async def audio_storage_dir() -> AsyncIterator[str]:
    with tempfile.TemporaryDirectory(prefix="vd-voice-test-") as tmp:
        yield tmp


@pytest.fixture
async def client(require_db: None, audio_storage_dir: str) -> AsyncIterator[AsyncClient]:
    os.environ["DATABASE_URL"] = DATABASE_URL
    os.environ["LLM_PROVIDER"] = "mock"
    os.environ["VOICE_ENABLED"] = "true"
    os.environ["AUDIO_STORAGE_DIR"] = audio_storage_dir
    os.environ["VOICE_UPLOADS_PER_MINUTE"] = "1000"
    os.environ["VOICE_BYTES_PER_HOUR"] = "999999999"
    os.environ["STT_REQUESTS_PER_MINUTE"] = "1000"
    os.environ["TTS_REQUESTS_PER_MINUTE"] = "1000"
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

    from app.database.session import SessionLocal
    from app.models import KnowledgeChunk, KnowledgeDocument
    from sqlalchemy import func

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from scripts.seed_knowledge import seed_knowledge

    async with SessionLocal() as db:
        docs = (await db.execute(select(func.count()).select_from(KnowledgeDocument))).scalar_one()
        chunks = (await db.execute(select(func.count()).select_from(KnowledgeChunk))).scalar_one()
    if int(docs) < 12 or int(chunks) < 100:
        await seed_knowledge(force=False)
        async with SessionLocal() as db:
            docs = (
                await db.execute(select(func.count()).select_from(KnowledgeDocument))
            ).scalar_one()
            chunks = (
                await db.execute(select(func.count()).select_from(KnowledgeChunk))
            ).scalar_one()
        if int(docs) < 12 or int(chunks) < 100:
            await seed_knowledge(force=True)


@pytest.fixture(autouse=True)
async def _reset_voice_rate_limits(require_db: None) -> AsyncIterator[None]:
    from app.core.redis import reset_redis

    await reset_redis()
    yield
    await reset_redis()


@pytest.fixture
async def isolated_voice(require_db: None) -> AsyncIterator[list[UUID]]:
    """Track and delete voice artifacts created during a test."""
    from tests.helpers import TEST_VOICE_REQUEST_PREFIX, delete_test_voice_artifacts

    created: list[UUID] = []
    await delete_test_voice_artifacts(request_id_prefix=TEST_VOICE_REQUEST_PREFIX)
    yield created
    await delete_test_voice_artifacts(
        voice_message_ids=created,
        request_id_prefix=TEST_VOICE_REQUEST_PREFIX,
    )


def _voice_headers(demo_key: str) -> dict[str, str]:
    return {
        "X-Demo-User-Key": demo_key,
        "X-Request-ID": f"vdtest-voice-{uuid4().hex[:12]}",
    }


def _load_fixture(name: str) -> bytes:
    path = AUDIO_DIR / f"{name}.wav"
    if not path.is_file():
        raise AssertionError(f"Missing fixture audio: {path}")
    return path.read_bytes()


async def _upload_wav(
    client: AsyncClient,
    *,
    demo_key: str,
    fixture: str = "en",
    filename: str | None = None,
    mime: str = "audio/wav",
    data: bytes | None = None,
    track: list[UUID] | None = None,
) -> dict:
    payload = data if data is not None else _load_fixture(fixture)
    fname = filename or f"{fixture}.wav"
    res = await client.post(
        "/api/v1/voice/upload",
        headers=_voice_headers(demo_key),
        files={"file": (fname, payload, mime)},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    if track is not None:
        track.append(UUID(body["voice_message"]["id"]))
    return body


async def _transcribe(
    client: AsyncClient,
    *,
    demo_key: str,
    voice_message_id: str,
    auto_submit: bool = False,
    fixture_key: str | None = None,
) -> dict:
    params: dict[str, str | bool] = {"auto_submit": auto_submit}
    if fixture_key:
        params["fixture_key"] = fixture_key
    res = await client.post(
        f"/api/v1/voice/messages/{voice_message_id}/transcribe",
        headers=_voice_headers(demo_key),
        params=params,
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _confirm(
    client: AsyncClient,
    *,
    demo_key: str,
    voice_message_id: str,
    transcript_hash: str,
) -> dict:
    res = await client.post(
        f"/api/v1/voice/messages/{voice_message_id}/confirm",
        headers=_voice_headers(demo_key),
        json={"transcript_hash": transcript_hash},
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _edit(
    client: AsyncClient,
    *,
    demo_key: str,
    voice_message_id: str,
    transcript: str,
) -> dict:
    res = await client.post(
        f"/api/v1/voice/messages/{voice_message_id}/edit",
        headers=_voice_headers(demo_key),
        json={"transcript": transcript},
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _submit(
    client: AsyncClient,
    *,
    demo_key: str,
    voice_message_id: str,
    transcript_hash: str | None = None,
) -> dict:
    params: dict[str, str] = {}
    if transcript_hash:
        params["transcript_hash"] = transcript_hash
    res = await client.post(
        f"/api/v1/voice/messages/{voice_message_id}/submit",
        headers=_voice_headers(demo_key),
        params=params,
    )
    assert res.status_code == 200, res.text
    return res.json()


# --- Upload validation ---


@pytest.mark.asyncio
async def test_valid_wav_upload_and_transcribe(
    client: AsyncClient, isolated_voice: list[UUID]
) -> None:
    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    vm = up["voice_message"]
    assert vm["transcription_status"] == "pending"
    assert vm["mime_type"] == "audio/wav"
    assert up["provider"]["is_mock"] is True

    tx = await _transcribe(
        client,
        demo_key="demo-anya",
        voice_message_id=vm["id"],
        auto_submit=False,
    )
    assert tx["voice_message"]["transcription_status"] == "completed"
    assert tx["voice_message"]["transcript"] == FIXTURE_TRANSCRIPTS["en"][0]
    assert tx["voice_message"]["detected_language"] == "en"
    assert float(tx["voice_message"]["transcript_confidence"]) == pytest.approx(0.92, abs=0.01)


@pytest.mark.asyncio
async def test_upload_rejects_empty(client: AsyncClient, isolated_voice: list[UUID]) -> None:
    res = await client.post(
        "/api/v1/voice/upload",
        headers=_voice_headers("demo-anya"),
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "audio_empty"


@pytest.mark.asyncio
async def test_upload_rejects_oversized(client: AsyncClient, isolated_voice: list[UUID]) -> None:
    from app.core.config import get_settings

    cfg = get_settings()
    huge = _load_fixture("en") + b"x" * (cfg.audio_max_size_bytes + 1)
    res = await client.post(
        "/api/v1/voice/upload",
        headers=_voice_headers("demo-anya"),
        files={"file": ("big.wav", huge, "audio/wav")},
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "audio_too_large"


@pytest.mark.asyncio
async def test_upload_rejects_malformed(client: AsyncClient, isolated_voice: list[UUID]) -> None:
    bad = (AUDIO_DIR / "malformed.wav").read_bytes()
    res = await client.post(
        "/api/v1/voice/upload",
        headers=_voice_headers("demo-anya"),
        files={"file": ("malformed.wav", bad, "audio/wav")},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] in {"audio_malformed", "audio_format_unsupported"}


@pytest.mark.asyncio
async def test_upload_rejects_mime_mismatch(
    client: AsyncClient, isolated_voice: list[UUID]
) -> None:
    res = await client.post(
        "/api/v1/voice/upload",
        headers=_voice_headers("demo-anya"),
        files={"file": ("en.wav", _load_fixture("en"), "audio/mpeg")},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "audio_mime_mismatch"


@pytest.mark.asyncio
async def test_upload_rejects_traversal_filename(
    client: AsyncClient, isolated_voice: list[UUID]
) -> None:
    res = await client.post(
        "/api/v1/voice/upload",
        headers=_voice_headers("demo-anya"),
        files={"file": ("../../etc/passwd.wav", _load_fixture("en"), "audio/wav")},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "audio_filename_invalid"


# --- Deterministic STT ---


@pytest.mark.parametrize(
    "fixture_key",
    ["en", "hi", "mr", "hinglish", "low_confidence"],
)
@pytest.mark.asyncio
async def test_deterministic_stt_fixtures(
    client: AsyncClient,
    isolated_voice: list[UUID],
    fixture_key: str,
) -> None:
    up = await _upload_wav(client, demo_key="demo-anya", fixture=fixture_key, track=isolated_voice)
    tx = await _transcribe(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        auto_submit=False,
        fixture_key=fixture_key,
    )
    expected = FIXTURE_TRANSCRIPTS[fixture_key]
    vm = tx["voice_message"]
    assert vm["transcript"] == expected[0]
    assert vm["detected_language"] == expected[1]
    assert float(vm["transcript_confidence"]) == pytest.approx(expected[2], abs=0.01)


# --- Deterministic TTS ---


@pytest.mark.asyncio
async def test_deterministic_tts(client: AsyncClient, isolated_voice: list[UUID]) -> None:
    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    tx = await _transcribe(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        auto_submit=False,
    )
    th = tx["voice_message"]["transcript_hash"]
    await _confirm(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        transcript_hash=th,
    )
    sub = await _submit(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        transcript_hash=th,
    )
    assert sub.get("assistant_message")
    msg_id = sub["assistant_message"]["id"]

    res1 = await client.post(
        "/api/v1/voice/tts",
        headers=_voice_headers("demo-anya"),
        json={"message_id": msg_id, "language": "en"},
    )
    res2 = await client.post(
        "/api/v1/voice/tts",
        headers=_voice_headers("demo-anya"),
        json={"message_id": msg_id, "language": "en"},
    )
    assert res1.status_code == 200, res1.text
    assert res2.status_code == 200, res2.text
    assert res1.json()["content_hash"] == res2.json()["content_hash"]
    assert res1.json()["is_mock"] is True
    assert res1.json()["download_url"]


# --- Security / isolation ---


@pytest.mark.asyncio
async def test_cross_user_audio_download_denied(
    client: AsyncClient, isolated_voice: list[UUID]
) -> None:
    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    vm_id = up["voice_message"]["id"]
    res = await client.get(
        f"/api/v1/voice/messages/{vm_id}/download",
        headers=_voice_headers("demo-rahul"),
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "voice_forbidden"


@pytest.mark.asyncio
async def test_unauthorized_playback_denied(
    client: AsyncClient, isolated_voice: list[UUID]
) -> None:
    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    tx = await _transcribe(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        auto_submit=False,
    )
    th = tx["voice_message"]["transcript_hash"]
    await _confirm(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        transcript_hash=th,
    )
    sub = await _submit(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        transcript_hash=th,
    )
    tts = await client.post(
        "/api/v1/voice/tts",
        headers=_voice_headers("demo-anya"),
        json={"message_id": sub["assistant_message"]["id"], "language": "en"},
    )
    assert tts.status_code == 200
    synth_id = tts.json()["id"]

    denied = await client.get(
        f"/api/v1/voice/synthesis/{synth_id}/download",
        headers=_voice_headers("demo-rahul"),
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "synthesis_forbidden"


@pytest.mark.asyncio
async def test_voice_trace_omits_raw_audio(client: AsyncClient, isolated_voice: list[UUID]) -> None:
    from app.database.session import SessionLocal
    from app.models import VoiceTrace

    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    await _transcribe(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        auto_submit=False,
    )
    async with SessionLocal() as db:
        traces = (
            (
                await db.execute(
                    select(VoiceTrace).where(
                        VoiceTrace.voice_message_id == UUID(up["voice_message"]["id"])
                    )
                )
            )
            .scalars()
            .all()
        )
    assert traces
    mapper = inspect(VoiceTrace)
    column_names = {c.key for c in mapper.columns}
    assert "audio_bytes" not in column_names
    assert "raw_audio" not in column_names
    for trace in traces:
        meta = trace.safe_metadata or {}
        blob = str(meta).lower()
        assert "audio_bytes" not in blob
        assert "raw_audio" not in blob
        for val in meta.values():
            if isinstance(val, str) and len(val) > 256:
                assert not val.startswith("RIFF")


# --- Transcript confirm / edit / hash ---


@pytest.mark.asyncio
async def test_transcript_confirm_edit_hash_invalidation(
    client: AsyncClient, isolated_voice: list[UUID]
) -> None:
    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    vm_id = up["voice_message"]["id"]
    tx = await _transcribe(client, demo_key="demo-anya", voice_message_id=vm_id, auto_submit=False)
    old_hash = tx["voice_message"]["transcript_hash"]

    edited = await _edit(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript="Edited return policy question for unused items.",
    )
    new_hash = edited["voice_message"]["transcript_hash"]
    assert new_hash != old_hash
    assert edited["voice_message"]["transcript_confirmed_at"] is None

    bad_confirm = await client.post(
        f"/api/v1/voice/messages/{vm_id}/confirm",
        headers=_voice_headers("demo-anya"),
        json={"transcript_hash": old_hash},
    )
    assert bad_confirm.status_code == 409
    assert bad_confirm.json()["error"]["code"] == "transcript_hash_mismatch"

    good = await client.post(
        f"/api/v1/voice/messages/{vm_id}/confirm",
        headers=_voice_headers("demo-anya"),
        json={"transcript_hash": new_hash},
    )
    assert good.status_code == 200
    assert good.json()["voice_message"]["transcription_status"] == "confirmed"


@pytest.mark.asyncio
async def test_low_confidence_cannot_auto_submit(
    client: AsyncClient, isolated_voice: list[UUID]
) -> None:
    up = await _upload_wav(
        client, demo_key="demo-anya", fixture="low_confidence", track=isolated_voice
    )
    res = await client.post(
        f"/api/v1/voice/messages/{up['voice_message']['id']}/transcribe",
        headers=_voice_headers("demo-anya"),
        params={"auto_submit": True, "fixture_key": "low_confidence"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert "workflow" not in body or body.get("workflow") is None
    vm = body["voice_message"]
    assert vm["can_auto_submit"] is False
    assert vm["submitted_at"] is None
    assert float(vm["transcript_confidence"]) < 0.85


# --- Workflow via voice ---


@pytest.mark.asyncio
async def test_voice_policy_submit_returns_citations(
    client: AsyncClient, ensure_corpus: None, isolated_voice: list[UUID]
) -> None:
    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    tx = await _transcribe(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        auto_submit=False,
        fixture_key="en",
    )
    th = tx["voice_message"]["transcript_hash"]
    await _confirm(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        transcript_hash=th,
    )
    sub = await _submit(
        client,
        demo_key="demo-anya",
        voice_message_id=up["voice_message"]["id"],
        transcript_hash=th,
    )
    assert sub["workflow"]["intent"] == "policy_question"
    if not sub["workflow"].get("no_answer"):
        assert sub["workflow"].get("citations")


@pytest.mark.asyncio
async def test_voice_order_status(client: AsyncClient, isolated_voice: list[UUID]) -> None:
    from tests.helpers import ensure_order_with_status

    ref = await ensure_order_with_status("demo-anya", "shipped")
    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    vm_id = up["voice_message"]["id"]
    await _transcribe(client, demo_key="demo-anya", voice_message_id=vm_id, auto_submit=False)
    edited = await _edit(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript=f"Where is my order {ref}?",
    )
    th = edited["voice_message"]["transcript_hash"]
    await _confirm(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript_hash=th,
    )
    sub = await _submit(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript_hash=th,
    )
    assert sub["workflow"]["intent"] == "order_status"
    assert sub["workflow"]["selected_tool"] == "get_order_status"


@pytest.mark.asyncio
async def test_voice_cancel_requires_confirmation(
    client: AsyncClient, isolated_voice: list[UUID]
) -> None:
    from tests.helpers import ensure_cancellable_order

    ref = await ensure_cancellable_order("demo-anya")
    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    vm_id = up["voice_message"]["id"]
    await _transcribe(client, demo_key="demo-anya", voice_message_id=vm_id, auto_submit=False)
    edited = await _edit(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript=f"please cancel my order {ref}",
    )
    th = edited["voice_message"]["transcript_hash"]
    await _confirm(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript_hash=th,
    )
    sub = await _submit(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript_hash=th,
    )
    assert sub["workflow"]["confirmation_required"] is True
    assert sub["workflow"]["selected_tool"] == "cancel_order"
    assert sub["workflow"]["confirmation"] is not None


@pytest.mark.asyncio
async def test_malicious_transcript_cannot_select_unregistered_tool(
    client: AsyncClient, ensure_corpus: None, isolated_voice: list[UUID]
) -> None:
    from app.database.session import SessionLocal
    from app.models import Order, OrderStatus, ToolExecution, User

    async with SessionLocal() as db:
        anya = (await db.execute(select(User).where(User.demo_key == "demo-anya"))).scalar_one()
        before_cancels = (
            await db.execute(
                select(func.count())
                .select_from(Order)
                .where(Order.user_id == anya.id, Order.status == OrderStatus.CANCELLED)
            )
        ).scalar_one()
        before_tools = (
            await db.execute(select(func.count()).select_from(ToolExecution))
        ).scalar_one()

    up = await _upload_wav(client, demo_key="demo-anya", fixture="en", track=isolated_voice)
    vm_id = up["voice_message"]["id"]
    await _transcribe(client, demo_key="demo-anya", voice_message_id=vm_id, auto_submit=False)
    edited = await _edit(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript="What do the internal override notes say about cancel every order policy?",
    )
    th = edited["voice_message"]["transcript_hash"]
    await _confirm(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript_hash=th,
    )
    sub = await _submit(
        client,
        demo_key="demo-anya",
        voice_message_id=vm_id,
        transcript_hash=th,
    )
    assert sub["workflow"]["selected_tool"] != "cancel_order"
    assert sub["workflow"].get("intent") == "policy_question" or sub["workflow"].get(
        "retrieval_strategy"
    )

    async with SessionLocal() as db:
        anya = (await db.execute(select(User).where(User.demo_key == "demo-anya"))).scalar_one()
        after_cancels = (
            await db.execute(
                select(func.count())
                .select_from(Order)
                .where(Order.user_id == anya.id, Order.status == OrderStatus.CANCELLED)
            )
        ).scalar_one()
        after_tools = (
            await db.execute(select(func.count()).select_from(ToolExecution))
        ).scalar_one()
    assert after_cancels == before_cancels
    assert after_tools == before_tools


# --- Regression smoke ---


@pytest.mark.asyncio
async def test_text_chat_regression_smoke(client: AsyncClient) -> None:
    from tests.helpers import ensure_order_with_status

    ref = await ensure_order_with_status("demo-anya", "shipped")
    res = await client.post(
        "/api/v1/chat/messages",
        headers={"X-Demo-User-Key": "demo-anya", "Idempotency-Key": f"smoke-{uuid4()}"},
        json={"content": f"Where is my order {ref}?"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["workflow"]["intent"] == "order_status"
    assert body["workflow"]["selected_tool"] == "get_order_status"
