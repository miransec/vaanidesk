from __future__ import annotations

import pytest
from app.main import create_app
from app.providers.base import ChatMessage
from app.providers.mock import MockChatProvider
from app.schemas.chat import ChatMessageCreate
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["service"] == "vaanidesk-backend"


@pytest.mark.asyncio
async def test_mock_provider_english() -> None:
    provider = MockChatProvider()
    result = await provider.complete(messages=[ChatMessage(role="user", content="hello")])
    assert result.is_mock is True
    assert result.provider == "mock"
    assert "production model" in result.content.lower() or "mock" in result.content.lower()
    assert result.language_hint == "en"


@pytest.mark.asyncio
async def test_mock_provider_hinglish() -> None:
    provider = MockChatProvider()
    result = await provider.complete(
        messages=[ChatMessage(role="user", content="mera order kahan hai")]
    )
    assert result.language_hint == "hinglish"
    assert "Phase 2" in result.content or "phase 2" in result.content.lower()


@pytest.mark.asyncio
async def test_mock_provider_hindi() -> None:
    provider = MockChatProvider()
    result = await provider.complete(messages=[ChatMessage(role="user", content="मेरा ऑर्डर कहाँ है")])
    assert result.language_hint == "hi"


@pytest.mark.asyncio
async def test_mock_provider_marathi() -> None:
    provider = MockChatProvider()
    result = await provider.complete(messages=[ChatMessage(role="user", content="माझी ऑर्डर कुठे आहे")])
    assert result.language_hint == "mr"


@pytest.mark.asyncio
async def test_chat_validation_requires_auth(app) -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/chat/messages", json={"content": "hello"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "demo_auth_required"


def test_chat_empty_content_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatMessageCreate(content="   ")
