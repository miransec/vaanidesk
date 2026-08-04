from __future__ import annotations

import pytest
from app.agents.intent import Intent, get_intent_classifier
from app.agents.language import get_language_detector
from app.main import create_app
from app.providers.base import ChatMessage
from app.providers.mock import MockChatProvider
from app.schemas.chat import ChatMessageCreate
from app.tools.registry import get_tool, is_registered, list_tools
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
    assert res.json()["error"]["code"] in ("demo_auth_required", "authentication_required")


def test_chat_empty_content_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatMessageCreate(content="   ")


def test_language_detection_suite() -> None:
    detector = get_language_detector()
    assert detector.detect("where is my order VD-10001").language_code == "en"
    assert detector.detect("mera order 1001 kidhar hai").language_code == "hinglish"
    assert detector.detect("मेरा ऑर्डर 1001 कहाँ है").language_code == "hi"
    assert detector.detect("माझी ऑर्डर 1001 कुठे आहे").language_code == "mr"


def test_intent_suite() -> None:
    detector = get_language_detector()
    classifier = get_intent_classifier()

    en = detector.detect("where is my order VD-10001")
    assert classifier.classify("where is my order VD-10001", en).intent == Intent.ORDER_STATUS

    hi_text = "मेरा ऑर्डर VD-10001 कहाँ है"
    hi = detector.detect(hi_text)
    assert classifier.classify(hi_text, hi).intent == Intent.ORDER_STATUS

    cancel = classifier.classify(
        "please cancel my order VD-10001", detector.detect("please cancel my order VD-10001")
    )
    assert cancel.intent == Intent.CANCEL_ORDER

    missing = classifier.classify("mera order kahan hai", detector.detect("mera order kahan hai"))
    assert missing.intent == Intent.ORDER_STATUS
    assert "order_ref" in missing.missing_fields

    human = classifier.classify(
        "I want to talk to a human", detector.detect("I want to talk to a human")
    )
    assert human.intent == Intent.HUMAN_ESCALATION

    unknown = classifier.classify("asdf qwerty", detector.detect("asdf qwerty"))
    assert unknown.intent == Intent.UNKNOWN


def test_tool_registry_allow_list() -> None:
    names = {t.name for t in list_tools()}
    assert "get_order_status" in names
    assert "cancel_order" in names
    assert is_registered("get_order_status")
    assert not is_registered("delete_everything")
    from app.core.errors import AppError

    with pytest.raises(AppError):
        get_tool("not_a_real_tool")
