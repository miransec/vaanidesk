"""Argument hashing and log redaction helpers."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_TOKEN_RE = re.compile(r"(confirmation[_-]?token|token|secret|password|api[_-]?key)", re.I)
_ADDRESS_RE = re.compile(r"(address|delivery_address|new_address)", re.I)
_SENSITIVE_TEXT_RE = re.compile(r"(description|issue|reason|content|message)", re.I)


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)


def argument_hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def _truncate(value: str, limit: int = 48) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "…"


def redact_mapping(data: dict[str, Any] | None) -> dict[str, Any] | None:
    """Redact secrets/tokens and truncate addresses / free-text in durable traces."""
    if data is None:
        return None
    out: dict[str, Any] = {}
    for key, value in data.items():
        if _TOKEN_RE.search(key):
            out[key] = "[REDACTED]"
        elif isinstance(value, dict):
            out[key] = redact_mapping(value)
        elif isinstance(value, str) and (key.lower().endswith("token") or _TOKEN_RE.search(key)):
            out[key] = "[REDACTED]"
        elif isinstance(value, str) and _ADDRESS_RE.search(key):
            out[key] = _truncate(value, 40)
        elif isinstance(value, str) and _SENSITIVE_TEXT_RE.search(key) and len(value) > 80:
            out[key] = _truncate(value, 80)
        else:
            out[key] = value
    return out


def safe_log_message(message: str) -> str:
    # Never log raw confirmation tokens if they leak into free text.
    return re.sub(
        r"\b[A-Za-z0-9_-]{32,}\b",
        "[REDACTED_OPAQUE]",
        message,
    )
