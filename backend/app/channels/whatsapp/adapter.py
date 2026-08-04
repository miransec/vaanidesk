"""WhatsApp Cloud API adapter — Meta-style webhook schema, signature verification."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from app.channels.base import (
    DeliveryResult,
    NormalizedAttachment,
    NormalizedMessage,
    NormalizedSender,
    OutboundPayload,
)
from app.channels.signatures import verify_hmac
from app.channels.whatsapp.simulator import record_outbound

logger = logging.getLogger(__name__)


class WhatsAppAdapter:
    """WhatsApp Cloud API adapter. Uses simulator for dev/test."""

    channel_type = "whatsapp"

    def validate_inbound_event(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        return len(raw_body) < 1_000_000

    def verify_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        signature = headers.get("x-hub-signature-256", headers.get("x-channel-signature", ""))
        timestamp = headers.get("x-channel-timestamp", "")
        event_id = headers.get("x-channel-event-id")
        if signature.startswith("sha256="):
            signature = signature[7:]
        return verify_hmac(
            raw_body=raw_body, signature=signature, timestamp=timestamp, event_id=event_id
        )

    def normalize_sender(self, payload: dict[str, Any]) -> NormalizedSender:
        phone = _extract_phone(payload)
        return NormalizedSender(
            external_id_hash=hashlib.sha256(phone.encode()).hexdigest(),
            display_name=_extract_display_name(payload),
        )

    def normalize_message(self, payload: dict[str, Any]) -> NormalizedMessage:
        text = _extract_text(payload)
        return NormalizedMessage(
            text=text[:4000],
            metadata={"wa_message_id": _extract_message_id(payload)},
        )

    def normalize_attachment(self, payload: dict[str, Any]) -> NormalizedAttachment | None:
        return None

    async def send_message(self, payload: OutboundPayload) -> DeliveryResult:
        record_outbound(recipient=payload.recipient_id, content=payload.content)
        return DeliveryResult(
            success=True,
            provider_message_id=f"wamid.mock-{hashlib.sha256(payload.content.encode()).hexdigest()[:12]}",
            provider_status="sent",
            response_code=200,
        )

    async def send_attachment(
        self, recipient_id: str, attachment_ref: str, content_type: str
    ) -> DeliveryResult:
        return DeliveryResult(success=True, provider_status="sent", response_code=200)

    async def query_delivery_status(self, provider_message_id: str) -> str:
        return "delivered"

    def verify_webhook_challenge(self, params: dict[str, str]) -> str | None:
        """Verify WhatsApp webhook challenge GET request."""
        from app.core.config import get_settings

        settings = get_settings()
        mode = params.get("hub.mode")
        token = params.get("hub.verify_token")
        challenge = params.get("hub.challenge")

        verify_token = getattr(settings, "whatsapp_verify_token", "vaanidesk-verify-change-me")
        if mode == "subscribe" and token == verify_token and challenge:
            return challenge
        return None


def _extract_phone(payload: dict[str, Any]) -> str:
    """Extract sender phone from Meta webhook format."""
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [{}])
        return str(messages[0].get("from", "unknown"))
    except (IndexError, KeyError, TypeError):
        return str(payload.get("from", "unknown"))


def _extract_display_name(payload: dict[str, Any]) -> str | None:
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        contacts = value.get("contacts", [{}])
        name = contacts[0].get("profile", {}).get("name")
        return str(name) if name is not None else None
    except (IndexError, KeyError, TypeError):
        return None


def _extract_text(payload: dict[str, Any]) -> str:
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [{}])
        msg = messages[0]
        body = msg.get("text", {}).get("body", "")
        if body:
            return str(body)
        return str(msg)
    except (IndexError, KeyError, TypeError):
        return str(payload.get("text") or payload.get("body") or "")


def _extract_message_id(payload: dict[str, Any]) -> str:
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [{}])
        return str(messages[0].get("id", ""))
    except (IndexError, KeyError, TypeError):
        return ""
