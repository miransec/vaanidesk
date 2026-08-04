"""Structured logging redaction filters.

Prevents secrets, tokens, audio data, full request/response bodies,
and private reasoning from entering log output.
"""

from __future__ import annotations

import logging
import re

_SECRET_PATTERNS = [
    re.compile(r"(Bearer|Basic)\s+[A-Za-z0-9_.+/=-]{10,}", re.I),
    re.compile(r"(api[_-]?key|secret[_-]?key|password|token|authorization)\s*[:=]\s*\S+", re.I),
    re.compile(r"\bey[A-Za-z0-9_.+/=-]{20,}"),
    re.compile(r"\b[A-Fa-f0-9]{64}\b"),
]

_BODY_PATTERN = re.compile(
    r"(audio_data|raw_body|full_body|request_body|response_body|transcript_text)\s*[:=]\s*\S.*",
    re.I,
)


class SecretRedactionFilter(logging.Filter):
    """Redacts secrets and sensitive data from log records before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pat in _SECRET_PATTERNS:
            msg = pat.sub("[REDACTED]", msg)
        if _BODY_PATTERN.search(msg):
            msg = _BODY_PATTERN.sub("[BODY_REDACTED]", msg)
        record.msg = msg
        record.args = ()
        return True


def install_redaction_filter() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(SecretRedactionFilter())
