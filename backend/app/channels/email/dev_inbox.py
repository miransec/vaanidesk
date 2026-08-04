"""Deterministic dev inbox — stores sent emails in memory for testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class DevEmail:
    recipient: str
    content: str
    sent_at: datetime = field(default_factory=lambda: datetime.now(UTC))


_inbox: list[DevEmail] = []


def record_outbound(*, recipient: str, content: str) -> None:
    _inbox.append(DevEmail(recipient=recipient, content=content))


def get_inbox() -> list[DevEmail]:
    return list(_inbox)


def clear_inbox() -> None:
    _inbox.clear()


def inbox_count() -> int:
    return len(_inbox)
