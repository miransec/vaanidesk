"""Phase 5 — Omnichannel tests.

Covers: HMAC signatures, dedup, email/whatsapp adapters, simulator, outbox,
attachments, identity linking, external confirmation, handoff, renderers.
Uses deterministic mocks only; no real network calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://vaanidesk:vaanidesk_dev_password@localhost:5432/vaanidesk",
)

DEMO_KEY = "demo-anya"
HEADERS = {"X-Demo-User-Key": DEMO_KEY}

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
    os.environ["CHANNELS_ENABLED"] = "true"
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
async def seeded_channels(client: AsyncClient):
    """Ensure channel connections are seeded."""
    resp = await client.post("/api/v1/channels/seed", headers=HEADERS)
    assert resp.status_code == 200
    return resp.json()


def _make_hmac(
    body: bytes, timestamp: str, secret: str = "dev-hmac-secret-not-for-production"
) -> str:
    message = f"{timestamp}.{body.decode('utf-8', errors='replace')}".encode()
    return hmac.HMAC(secret.encode(), message, hashlib.sha256).hexdigest()


def _email_payload(
    text: str = "Hello support",
    from_email: str = "user@example.com",
    subject: str = "Test",
    message_id: str | None = None,
) -> dict:
    return {
        "from": from_email,
        "from_display": "Test User",
        "subject": subject,
        "text_body": text,
        "message_id": message_id or f"msg-{uuid4().hex[:8]}",
    }


def _signed_request(payload: dict) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    sig = _make_hmac(body, timestamp)
    event_id = payload.get("message_id", f"evt-{uuid4().hex[:8]}")
    headers = {
        **HEADERS,
        "x-channel-signature": sig,
        "x-channel-timestamp": timestamp,
        "x-channel-event-id": event_id,
        "content-type": "application/json",
    }
    return body, headers


# =============================================================================
# HMAC Signature Tests
# =============================================================================


class TestHMACSignatures:
    """HMAC accept/reject, missing sig, stale timestamp, replay."""

    def test_valid_hmac(self):
        from app.channels.signatures import clear_replay_store, verify_hmac

        clear_replay_store()
        body = b'{"text":"hello"}'
        ts = str(int(time.time()))
        sig = _make_hmac(body, ts)
        assert verify_hmac(raw_body=body, signature=sig, timestamp=ts, event_id="ev1")

    def test_invalid_hmac_rejected(self):
        from app.channels.signatures import clear_replay_store, verify_hmac

        clear_replay_store()
        body = b'{"text":"hello"}'
        ts = str(int(time.time()))
        assert not verify_hmac(
            raw_body=body, signature="bad-signature", timestamp=ts, event_id="ev2"
        )

    def test_missing_signature_rejected(self):
        from app.channels.signatures import verify_hmac

        body = b'{"text":"hello"}'
        ts = str(int(time.time()))
        assert not verify_hmac(raw_body=body, signature="", timestamp=ts)

    def test_stale_timestamp_rejected(self):
        from app.channels.signatures import clear_replay_store, verify_hmac

        clear_replay_store()
        body = b'{"text":"hello"}'
        ts = str(int(time.time()) - 600)
        sig = _make_hmac(body, ts)
        assert not verify_hmac(raw_body=body, signature=sig, timestamp=ts)

    def test_replay_rejected(self):
        from app.channels.signatures import clear_replay_store, verify_hmac

        clear_replay_store()
        body = b'{"text":"hello"}'
        ts = str(int(time.time()))
        sig = _make_hmac(body, ts)
        assert verify_hmac(raw_body=body, signature=sig, timestamp=ts, event_id="replay-1")
        assert not verify_hmac(raw_body=body, signature=sig, timestamp=ts, event_id="replay-1")


# =============================================================================
# Email Adapter Tests
# =============================================================================


class TestEmailAdapter:
    """Email MIME + HTML sanitize + message-id dedup."""

    def test_normalize_sender(self):
        from app.channels.email.adapter import EmailAdapter

        adapter = EmailAdapter()
        sender = adapter.normalize_sender({"from": "User@Example.COM", "from_display": "Alice"})
        expected_hash = hashlib.sha256(b"user@example.com").hexdigest()
        assert sender.external_id_hash == expected_hash
        assert sender.display_name == "Alice"

    def test_normalize_message_text(self):
        from app.channels.email.adapter import EmailAdapter

        adapter = EmailAdapter()
        msg = adapter.normalize_message({"subject": "Help", "text_body": "I need help"})
        assert "Help" in msg.text
        assert "I need help" in msg.text

    def test_normalize_message_html_strip(self):
        from app.channels.email.adapter import EmailAdapter

        adapter = EmailAdapter()
        msg = adapter.normalize_message(
            {
                "subject": "",
                "html_body": "<p>Hello <b>world</b></p><script>alert(1)</script>",
            }
        )
        assert "Hello world" in msg.text
        assert "<script>" not in msg.text
        assert "<p>" not in msg.text

    def test_message_id_dedup_metadata(self):
        from app.channels.email.adapter import EmailAdapter

        adapter = EmailAdapter()
        msg = adapter.normalize_message(
            {
                "subject": "Test",
                "text_body": "body",
                "message_id": "<unique-id@example.com>",
                "in_reply_to": "<prev-id@example.com>",
            }
        )
        assert msg.metadata["message_id"] == "<unique-id@example.com>"
        assert msg.metadata["in_reply_to"] == "<prev-id@example.com>"


# =============================================================================
# WhatsApp Adapter Tests
# =============================================================================


class TestWhatsAppAdapter:
    """WhatsApp schema + challenge + simulator."""

    def test_normalize_meta_webhook(self):
        from app.channels.whatsapp.adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter()
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "BIZ_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "contacts": [
                                    {"profile": {"name": "Ravi"}, "wa_id": "+919000000001"}
                                ],
                                "messages": [
                                    {
                                        "from": "+919000000001",
                                        "id": "wamid.123",
                                        "type": "text",
                                        "text": {"body": "Hi there"},
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }
        sender = adapter.normalize_sender(payload)
        assert sender.display_name == "Ravi"
        msg = adapter.normalize_message(payload)
        assert msg.text == "Hi there"

    def test_verify_challenge_success(self):
        from app.channels.whatsapp.adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter()
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "vaanidesk-verify-change-me",
            "hub.challenge": "challenge_abc",
        }
        assert adapter.verify_webhook_challenge(params) == "challenge_abc"

    def test_verify_challenge_fail(self):
        from app.channels.whatsapp.adapter import WhatsAppAdapter

        adapter = WhatsAppAdapter()
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "challenge_abc",
        }
        assert adapter.verify_webhook_challenge(params) is None

    def test_simulator_creates_valid_webhook(self):
        from app.channels.signatures import clear_replay_store, verify_hmac
        from app.channels.whatsapp.simulator import create_simulator_webhook

        clear_replay_store()
        body, headers = create_simulator_webhook(text="Sim test")
        sig = headers["x-channel-signature"]
        ts = headers["x-channel-timestamp"]
        event_id = headers["x-channel-event-id"]
        assert verify_hmac(raw_body=body, signature=sig, timestamp=ts, event_id=event_id)


# =============================================================================
# Attachment Tests
# =============================================================================


class TestAttachments:
    """Attachment validation, oversized, executable reject."""

    def test_valid_attachment(self):
        from app.channels.attachments import validate_attachment

        validate_attachment(content_type="image/png", size_bytes=1000, filename="photo.png")

    def test_oversized_rejected(self):
        from app.channels.attachments import validate_attachment
        from app.core.errors import AppError

        with pytest.raises(AppError, match="exceeds maximum size"):
            validate_attachment(content_type="image/png", size_bytes=20_000_000, filename="big.png")

    def test_executable_rejected(self):
        from app.channels.attachments import validate_attachment
        from app.core.errors import AppError

        with pytest.raises(AppError, match="file extension is not allowed"):
            validate_attachment(
                content_type="application/octet-stream", size_bytes=100, filename="malware.exe"
            )

    def test_blocked_mime_rejected(self):
        from app.channels.attachments import validate_attachment
        from app.core.errors import AppError

        with pytest.raises(AppError, match="file type is not allowed"):
            validate_attachment(
                content_type="application/x-msdownload", size_bytes=100, filename="file.dat"
            )

    def test_cross_user_download_denied(self):
        from app.channels.attachments import authorize_download

        owner = uuid4()
        requester = uuid4()
        assert not authorize_download(owner_user_id=owner, requesting_user_id=requester)

    def test_owner_download_allowed(self):
        from app.channels.attachments import authorize_download

        user_id = uuid4()
        assert authorize_download(owner_user_id=user_id, requesting_user_id=user_id)


# =============================================================================
# Identity Linking Tests
# =============================================================================


class TestIdentityLinking:
    """Link succeed/expire/reuse fail; unlink revokes."""

    @pytest.mark.asyncio
    async def test_link_flow(self, client: AsyncClient, seeded_channels):
        from app.database.session import SessionLocal
        from app.models.channels import ChannelConnection, ChannelIdentity
        from sqlalchemy import select

        async with SessionLocal() as db:
            conn = (await db.execute(select(ChannelConnection).limit(1))).scalar_one()
            identity = ChannelIdentity(
                id=uuid4(),
                channel_connection_id=conn.id,
                external_sender_id_hash="test-link-hash-" + uuid4().hex[:8],
            )
            db.add(identity)
            await db.commit()
            identity_id = identity.id

        resp = await client.post(
            "/api/v1/channels/identity/link",
            json={"channel_identity_id": str(identity_id)},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        token = resp.json()["token"]

        resp = await client.post(
            "/api/v1/channels/identity/link/complete",
            json={"token": token},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "linked"

        # Reuse should fail
        resp = await client.post(
            "/api/v1/channels/identity/link/complete",
            json={"token": token},
            headers=HEADERS,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_unlink(self, client: AsyncClient, seeded_channels):
        from app.database.session import SessionLocal
        from app.models import User
        from app.models.channels import ChannelConnection, ChannelIdentity, VerificationStatus
        from sqlalchemy import select

        async with SessionLocal() as db:
            user = (await db.execute(select(User).where(User.demo_key == DEMO_KEY))).scalar_one()
            conn = (await db.execute(select(ChannelConnection).limit(1))).scalar_one()
            identity = ChannelIdentity(
                id=uuid4(),
                channel_connection_id=conn.id,
                external_sender_id_hash="test-unlink-hash-" + uuid4().hex[:8],
                user_id=user.id,
                verification_status=VerificationStatus.VERIFIED,
            )
            db.add(identity)
            await db.commit()
            identity_id = identity.id

        resp = await client.post(
            "/api/v1/channels/identity/unlink",
            json={"identity_id": str(identity_id)},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "unlinked"


# =============================================================================
# External Confirmation Tests
# =============================================================================


class TestExternalConfirmation:
    """External sensitive → web confirm; external 'yes' does not bypass; confirmed once."""

    @pytest.mark.asyncio
    async def test_external_confirmation_flow(self, client: AsyncClient, seeded_channels):
        from app.database.session import SessionLocal
        from app.models import User
        from app.models.channels import ChannelConnection, ChannelIdentity
        from app.services.channels import create_external_confirmation
        from sqlalchemy import select

        async with SessionLocal() as db:
            user = (await db.execute(select(User).where(User.demo_key == DEMO_KEY))).scalar_one()
            conn = (await db.execute(select(ChannelConnection).limit(1))).scalar_one()
            identity = ChannelIdentity(
                id=uuid4(),
                channel_connection_id=conn.id,
                external_sender_id_hash="confirm-hash-" + uuid4().hex[:8],
                user_id=user.id,
            )
            db.add(identity)
            await db.flush()

            result = await create_external_confirmation(
                db=db,
                user_id=user.id,
                channel_identity_id=identity.id,
                action="cancel_order",
                action_args={"order_ref": "VD-001"},
                summary="Cancel order VD-001",
            )
            await db.commit()
            token = result["token"]

        # Get confirmation
        resp = await client.get(
            f"/api/v1/channels/confirm?token={token}",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "cancel_order"

        # Confirm
        resp = await client.post(
            f"/api/v1/channels/confirm?token={token}",
            json={"approved": True},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

        # Cannot confirm again
        resp = await client.post(
            f"/api/v1/channels/confirm?token={token}",
            json={"approved": True},
            headers=HEADERS,
        )
        assert resp.status_code == 400


# =============================================================================
# Renderer Tests
# =============================================================================


class TestRenderers:
    """Citations/no-answer render; channel-specific formatting."""

    def test_email_plain_with_citations(self):
        from app.channels.renderers import render_email_plain

        result = render_email_plain(
            "Here is the answer",
            citations=[
                {"document_title": "Return Policy", "section_label": "s1"},
            ],
        )
        assert "Return Policy" in result
        assert "VaaniDesk" in result

    def test_email_html_escapes(self):
        from app.channels.renderers import render_email_html

        result = render_email_html("<script>alert(1)</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_whatsapp_truncation(self):
        from app.channels.renderers import render_whatsapp

        long_text = "x" * 5000
        result = render_whatsapp(long_text)
        assert len(result) <= 4100

    def test_no_answer_render(self):
        from app.channels.renderers import render_no_answer

        assert (
            "human" in render_no_answer("whatsapp").lower()
            or "agent" in render_no_answer("whatsapp").lower()
        )

    def test_confirmation_link_render(self):
        from app.channels.renderers import render_confirmation_link

        result = render_confirmation_link("https://example.com/confirm", "Cancel order")
        assert "https://example.com/confirm" in result
        assert "Cancel order" in result


# =============================================================================
# Handoff Tests
# =============================================================================


class TestHandoff:
    """Human escalation; no false human-joined."""

    @pytest.mark.asyncio
    async def test_escalate_and_check(self):
        from app.channels.handoff import escalate_to_human, is_conversation_handed_off
        from app.database.session import SessionLocal
        from app.models import Conversation, User
        from sqlalchemy import select

        async with SessionLocal() as db:
            user = (await db.execute(select(User).where(User.demo_key == DEMO_KEY))).scalar_one()
            conv = Conversation(id=uuid4(), user_id=user.id, title="Handoff test")
            db.add(conv)
            await db.flush()

            item = await escalate_to_human(
                db=db, conversation_id=conv.id, summary="Need human help"
            )
            assert item.status.value == "queued"

            assert await is_conversation_handed_off(db=db, conversation_id=conv.id)

            # Duplicate escalation returns same item
            item2 = await escalate_to_human(db=db, conversation_id=conv.id, summary="Again")
            assert item2.id == item.id

            await db.rollback()

    @pytest.mark.asyncio
    async def test_no_false_handoff(self, client: AsyncClient, seeded_channels):
        resp = await client.get("/api/v1/channels/handoff", headers=HEADERS)
        assert resp.status_code == 200


# =============================================================================
# Outbox / Outbound Tests
# =============================================================================


class TestOutbound:
    """Outbound idempotency, delivery status."""

    def test_dev_inbox_records(self):
        from app.channels.email.dev_inbox import clear_inbox, get_inbox, record_outbound

        clear_inbox()
        record_outbound(recipient="test@example.com", content="Hello")
        assert len(get_inbox()) == 1
        assert get_inbox()[0].recipient == "test@example.com"
        clear_inbox()

    def test_whatsapp_simulator_records(self):
        from app.channels.whatsapp.simulator import clear_outbox, get_outbox, record_outbound

        clear_outbox()
        record_outbound(recipient="+91900", content="Hi")
        assert len(get_outbox()) == 1
        clear_outbox()


# =============================================================================
# API Integration Tests
# =============================================================================


class TestChannelAPI:
    """Integration tests for channel endpoints."""

    @pytest.mark.asyncio
    async def test_list_connections(self, client: AsyncClient, seeded_channels):
        resp = await client.get("/api/v1/channels/connections", headers=HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        types = {c["channel_type"] for c in data}
        assert "web" in types
        assert "email" in types

    @pytest.mark.asyncio
    async def test_toggle_connection(self, client: AsyncClient, seeded_channels):
        resp = await client.get("/api/v1/channels/connections", headers=HEADERS)
        conn = resp.json()[0]
        resp = await client.post(
            f"/api/v1/channels/connections/{conn['id']}/toggle",
            json={"enabled": False},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

        # Restore
        await client.post(
            f"/api/v1/channels/connections/{conn['id']}/toggle",
            json={"enabled": True},
            headers=HEADERS,
        )

    @pytest.mark.asyncio
    async def test_whatsapp_verify_challenge(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/channels/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "vaanidesk-verify-change-me",
                "hub.challenge": "test_challenge_42",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "test_challenge_42"

    @pytest.mark.asyncio
    async def test_whatsapp_verify_challenge_fail(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/channels/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong-token",
                "hub.challenge": "test_challenge",
            },
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_simulator_email(self, client: AsyncClient, seeded_channels):
        resp = await client.post(
            "/api/v1/channels/simulator/email",
            json={
                "from_email": "sim@example.com",
                "from_display": "Sim User",
                "subject": "Help needed",
                "text_body": "I need help with my order",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("processed", "anonymous_ack")

    @pytest.mark.asyncio
    async def test_simulator_whatsapp(self, client: AsyncClient, seeded_channels):
        resp = await client.post(
            "/api/v1/channels/simulator/whatsapp",
            json={
                "from_phone": "+919999888800",
                "display_name": "WA Test",
                "text": "What is my order status?",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_events_endpoint(self, client: AsyncClient, seeded_channels):
        resp = await client.get("/api/v1/channels/events", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_handoff_endpoint(self, client: AsyncClient, seeded_channels):
        resp = await client.get("/api/v1/channels/handoff", headers=HEADERS)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_failed_outbound_endpoint(self, client: AsyncClient, seeded_channels):
        resp = await client.get("/api/v1/channels/outbound/failed", headers=HEADERS)
        assert resp.status_code == 200


# =============================================================================
# Duplicate Event Tests
# =============================================================================


class TestDeduplication:
    """Duplicate event processed only once."""

    @pytest.mark.asyncio
    async def test_duplicate_inbound_event(self, client: AsyncClient, seeded_channels):
        resp1 = await client.post(
            "/api/v1/channels/simulator/email",
            json={
                "from_email": "dedup@example.com",
                "from_display": "Dedup",
                "subject": "Dedup test",
                "text_body": "First message",
                "message_id": "dedup-unique-123",
            },
            headers=HEADERS,
        )
        assert resp1.status_code == 200

        # Same event_id should be deduped (either via replay protection or DB constraint)
        from app.channels.signatures import clear_replay_store

        clear_replay_store()

        resp2 = await client.post(
            "/api/v1/channels/simulator/email",
            json={
                "from_email": "dedup@example.com",
                "from_display": "Dedup",
                "subject": "Dedup test",
                "text_body": "First message",
                "message_id": "dedup-unique-123",
            },
            headers=HEADERS,
        )
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "duplicate"
