from __future__ import annotations

import re
from typing import Any

from app.providers.base import ChatCompletionResult, ChatMessage


class MockChatProvider:
    """Deterministic offline provider for Phase 1 demos and tests.

    This is NOT a production model. Responses are pattern-based fixtures.
    """

    provider_name = "mock"
    model_name = "vaanidesk-mock-v1"

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        request_id: str | None = None,
    ) -> ChatCompletionResult:
        user_text = _last_user_text(messages)
        normalized = _normalize(user_text)
        language_hint, content = _respond(normalized, user_text)
        metadata: dict[str, Any] = {
            "provider": self.provider_name,
            "model": self.model_name,
            "is_mock": True,
            "disclaimer": "Mock provider — not a production LLM",
            "request_id": request_id,
            "matched_language_hint": language_hint,
        }
        return ChatCompletionResult(
            content=content,
            provider=self.provider_name,
            model=self.model_name,
            is_mock=True,
            language_hint=language_hint,
            metadata=metadata,
        )


def _last_user_text(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content.strip()
    return ""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _respond(normalized: str, original: str) -> tuple[str, str]:
    # Greetings
    if normalized in {"hello", "hi", "hey", "good morning", "good evening"}:
        return (
            "en",
            "Hello! I'm VaaniDesk's mock support assistant (not a production model). "
            "Ask about an order, or say namaste / नमस्ते / नमस्कार.",
        )
    if normalized in {"namaste", "namaskar", "नमस्ते", "नमस्कार"}:
        return (
            "hi",
            "नमस्ते! मैं VaaniDesk का mock सहायक हूँ (असली production model नहीं)। "
            "ऑर्डर की स्थिति पूछ सकते हैं — Phase 1 में deterministic demo जवाब मिलेंगे।",
        )

    # Order status patterns — English / Hinglish / Hindi / Marathi
    order_patterns = [
        (r"where\s+is\s+(my\s+)?order", "en"),
        (r"order\s+status", "en"),
        (r"mera\s+order\s+(kahan|kidhar|kaha)", "hinglish"),
        (r"mera\s+order", "hinglish"),
        (r"order\s+kahan", "hinglish"),
        (r"मेरा\s+ऑर्डर", "hi"),
        (r"ऑर्डर\s+कहाँ", "hi"),
        (r"माझी\s+ऑर्डर", "mr"),
        (r"ऑर्डर\s+कुठे", "mr"),
    ]
    for pattern, lang in order_patterns:
        if re.search(pattern, normalized) or re.search(pattern, original, flags=re.IGNORECASE):
            return lang, _order_reply(lang)

    if any(token in normalized for token in ("help", "madad", "मदद", "मदत")):
        return (
            "en",
            "I can demo greetings and simple order-status phrasing in English, Hindi, "
            "Hinglish, and Marathi. Full tool calling arrives in Phase 2. "
            "(Mock provider — not a production model.)",
        )

    return (
        "en",
        "Thanks for your message. Phase 1 uses a deterministic mock provider "
        "(not a production model). Try: hello, namaste, 'mera order kahan hai', "
        "'मेरा ऑर्डर कहाँ है', or 'माझी ऑर्डर कुठे आहे'.",
    )


def _order_reply(lang: str) -> str:
    if lang == "hinglish":
        return (
            "Samajh gaya — aap order status pooch rahe ho. "
            "Phase 1 mein main sirf demo reply de sakta hoon; asli order lookup tools "
            "Phase 2 mein aayenge. (Mock provider — production model nahi.)"
        )
    if lang == "hi":
        return (
            "समझ गया — आप ऑर्डर की स्थिति पूछ रहे हैं। "
            "Phase 1 में यह केवल डेमो जवाब है; असली ऑर्डर टूल Phase 2 में आएंगे। "
            "(Mock provider — production model नहीं।)"
        )
    if lang == "mr":
        return (
            "समजलो — तुम्ही ऑर्डर स्थिती विचारत आहात. "
            "Phase 1 मध्ये हा फक्त डेमो प्रतिसाद आहे; खरे ऑर्डर टूल्स Phase 2 मध्ये येतील. "
            "(Mock provider — production model नाही.)"
        )
    return (
        "I understand you're asking about an order. "
        "Phase 1 returns a deterministic demo reply only — real order tools arrive in Phase 2. "
        "(Mock provider — not a production model.)"
    )
