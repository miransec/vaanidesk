"""WhatsApp simulator for local/dev testing — deterministic mock."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings


@dataclass
class SimulatedMessage:
    recipient: str
    content: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


_outbox: list[SimulatedMessage] = []


def record_outbound(*, recipient: str, content: str) -> None:
    _outbox.append(SimulatedMessage(recipient=recipient, content=content))


def get_outbox() -> list[SimulatedMessage]:
    return list(_outbox)


def clear_outbox() -> None:
    _outbox.clear()


def create_simulator_webhook(
    *,
    from_phone: str = "+919876543210",
    display_name: str = "Test User",
    text: str = "Hello from WhatsApp simulator",
    message_id: str | None = None,
) -> tuple[bytes, dict[str, str]]:
    """Create a simulated WhatsApp webhook payload with valid HMAC signature."""
    settings = get_settings()
    secret = getattr(settings, "channel_hmac_secret", "dev-hmac-secret-not-for-production")
    msg_id = message_id or f"wamid.sim-{int(time.time())}"
    timestamp = str(int(time.time()))

    payload: dict[str, Any] = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BUSINESS_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15551234567",
                                "phone_number_id": "PHONE_ID",
                            },
                            "contacts": [{"profile": {"name": display_name}, "wa_id": from_phone}],
                            "messages": [
                                {
                                    "from": from_phone,
                                    "id": msg_id,
                                    "timestamp": timestamp,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    body = json.dumps(payload).encode()
    message_bytes = f"{timestamp}.{body.decode()}".encode()
    sig = hmac.HMAC(secret.encode(), message_bytes, hashlib.sha256).hexdigest()

    headers = {
        "x-channel-signature": sig,
        "x-channel-timestamp": timestamp,
        "x-channel-event-id": msg_id,
        "content-type": "application/json",
    }

    return body, headers


def create_challenge_request(verify_token: str | None = None) -> dict[str, str]:
    """Create simulated WhatsApp verification challenge params."""
    settings = get_settings()
    token = verify_token or getattr(settings, "whatsapp_verify_token", "vaanidesk-verify-change-me")
    return {
        "hub.mode": "subscribe",
        "hub.verify_token": str(token),
        "hub.challenge": "mock_challenge_string_12345",
    }
