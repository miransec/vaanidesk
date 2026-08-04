"""Channel adapter protocol / ABC."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class NormalizedSender:
    external_id_hash: str
    display_name: str | None = None


@dataclass
class NormalizedMessage:
    text: str
    language_hint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedAttachment:
    content_type: str
    size_bytes: int
    content_hash: str
    data: bytes = b""


@dataclass
class OutboundPayload:
    recipient_id: str
    content: str
    message_type: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryResult:
    success: bool
    provider_message_id: str | None = None
    provider_status: str | None = None
    response_code: int | None = None
    error_code: str | None = None


class ChannelAdapter(Protocol):
    """Protocol for channel adapters."""

    channel_type: str

    def validate_inbound_event(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        """Check size/format constraints before signature verification."""
        ...

    def verify_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        """Verify HMAC/signature. Must fail closed."""
        ...

    def normalize_sender(self, payload: dict[str, Any]) -> NormalizedSender:
        """Extract sender identity from parsed payload."""
        ...

    def normalize_message(self, payload: dict[str, Any]) -> NormalizedMessage:
        """Extract normalized message content."""
        ...

    def normalize_attachment(self, payload: dict[str, Any]) -> NormalizedAttachment | None:
        """Extract attachment if present."""
        ...

    async def send_message(self, payload: OutboundPayload) -> DeliveryResult:
        """Send outbound message through the channel."""
        ...

    async def send_attachment(
        self, recipient_id: str, attachment_ref: str, content_type: str
    ) -> DeliveryResult:
        """Send attachment through the channel."""
        ...

    async def query_delivery_status(self, provider_message_id: str) -> str:
        """Query delivery status from provider."""
        ...
