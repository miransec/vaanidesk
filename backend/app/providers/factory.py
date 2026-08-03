from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.errors import AppError
from app.providers.base import ChatProvider
from app.providers.mock import MockChatProvider


@lru_cache
def get_chat_provider() -> ChatProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockChatProvider()
    raise AppError(
        code="provider_unavailable",
        message=(
            f"LLM provider '{settings.llm_provider}' is not implemented in Phase 1. "
            "Use LLM_PROVIDER=mock."
        ),
        status_code=501,
    )
