"""AI provider interfaces — Phase 1 ships mock chat only."""

from app.providers.base import ChatCompletionResult, ChatMessage, ChatProvider
from app.providers.factory import get_chat_provider
from app.providers.mock import MockChatProvider

__all__ = [
    "ChatCompletionResult",
    "ChatMessage",
    "ChatProvider",
    "MockChatProvider",
    "get_chat_provider",
]
