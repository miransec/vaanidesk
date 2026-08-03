from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatCompletionResult:
    content: str
    provider: str
    model: str
    is_mock: bool
    language_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChatProvider(Protocol):
    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        request_id: str | None = None,
    ) -> ChatCompletionResult: ...
