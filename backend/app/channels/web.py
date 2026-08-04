"""Web channel adapter — thin passthrough noting web chat already exists."""

from __future__ import annotations

from typing import Any

from app.channels.base import (
    DeliveryResult,
    NormalizedAttachment,
    NormalizedMessage,
    NormalizedSender,
    OutboundPayload,
)


class WebAdapter:
    """Thin web adapter — web chat uses the existing REST API directly."""

    channel_type = "web"

    def validate_inbound_event(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        return True

    def verify_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        return True

    def normalize_sender(self, payload: dict[str, Any]) -> NormalizedSender:
        return NormalizedSender(
            external_id_hash=payload.get("user_id_hash", "web-user"),
            display_name=payload.get("display_name"),
        )

    def normalize_message(self, payload: dict[str, Any]) -> NormalizedMessage:
        return NormalizedMessage(text=payload.get("content", ""))

    def normalize_attachment(self, payload: dict[str, Any]) -> NormalizedAttachment | None:
        return None

    async def send_message(self, payload: OutboundPayload) -> DeliveryResult:
        return DeliveryResult(success=True, provider_status="delivered")

    async def send_attachment(
        self, recipient_id: str, attachment_ref: str, content_type: str
    ) -> DeliveryResult:
        return DeliveryResult(success=True, provider_status="delivered")

    async def query_delivery_status(self, provider_message_id: str) -> str:
        return "delivered"
