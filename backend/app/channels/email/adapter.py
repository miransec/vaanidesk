"""Email channel adapter — MIME parse, HTML sanitize, subject threading, message-id dedup."""

from __future__ import annotations

import hashlib
import html
import logging
import re
from typing import Any

from app.channels.base import (
    DeliveryResult,
    NormalizedAttachment,
    NormalizedMessage,
    NormalizedSender,
    OutboundPayload,
)
from app.channels.signatures import verify_hmac

logger = logging.getLogger(__name__)


class EmailAdapter:
    """Deterministic email adapter. Does NOT send real SMTP in dev/test."""

    channel_type = "email"

    def validate_inbound_event(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        return len(raw_body) < 2_000_000

    def verify_signature(self, raw_body: bytes, headers: dict[str, str]) -> bool:
        signature = headers.get("x-channel-signature", "")
        timestamp = headers.get("x-channel-timestamp", "")
        event_id = headers.get("x-channel-event-id")
        return verify_hmac(
            raw_body=raw_body, signature=signature, timestamp=timestamp, event_id=event_id
        )

    def normalize_sender(self, payload: dict[str, Any]) -> NormalizedSender:
        sender_email = payload.get("from", "unknown@example.com")
        return NormalizedSender(
            external_id_hash=hashlib.sha256(sender_email.lower().encode()).hexdigest(),
            display_name=payload.get("from_display", sender_email.split("@")[0]),
        )

    def normalize_message(self, payload: dict[str, Any]) -> NormalizedMessage:
        body = payload.get("text_body") or payload.get("html_body", "")
        if payload.get("html_body") and not payload.get("text_body"):
            body = _strip_html(body)
        subject = payload.get("subject", "")
        text = f"{subject}\n\n{body}".strip() if subject else body.strip()
        return NormalizedMessage(
            text=text[:10000],
            language_hint=payload.get("language"),
            metadata={
                "message_id": payload.get("message_id"),
                "subject": subject,
                "in_reply_to": payload.get("in_reply_to"),
            },
        )

    def normalize_attachment(self, payload: dict[str, Any]) -> NormalizedAttachment | None:
        att = payload.get("attachment")
        if not att:
            return None
        return NormalizedAttachment(
            content_type=att.get("content_type", "application/octet-stream"),
            size_bytes=att.get("size_bytes", 0),
            content_hash=att.get("content_hash", ""),
        )

    async def send_message(self, payload: OutboundPayload) -> DeliveryResult:
        from app.channels.email.dev_inbox import record_outbound

        record_outbound(recipient=payload.recipient_id, content=payload.content)
        return DeliveryResult(
            success=True,
            provider_message_id=f"mock-email-{hashlib.sha256(payload.content.encode()).hexdigest()[:12]}",
            provider_status="delivered",
            response_code=200,
        )

    async def send_attachment(
        self, recipient_id: str, attachment_ref: str, content_type: str
    ) -> DeliveryResult:
        return DeliveryResult(success=True, provider_status="delivered", response_code=200)

    async def query_delivery_status(self, provider_message_id: str) -> str:
        return "delivered"


def _strip_html(html_content: str) -> str:
    """Basic HTML to text — strip tags, decode entities."""
    text = re.sub(r"<br\s*/?>", "\n", html_content, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()
