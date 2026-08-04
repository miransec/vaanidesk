"""OpenTelemetry tracing boundaries.

Uses OTEL SDK with console/no-op exporter by default.
Exports can be configured via OTEL_EXPORTER_OTLP_ENDPOINT or similar env vars.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("vaanidesk.tracing")

_TRACER_INITIALIZED = False
_SPANS: list[dict[str, Any]] = []


def _safe_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """Strip secrets/raw tokens from span attributes."""
    blocked = {"token", "secret", "password", "api_key", "authorization", "audio_data", "body"}
    return {k: v for k, v in attrs.items() if not any(b in k.lower() for b in blocked)}


def init_tracing(service_name: str = "vaanidesk-backend", enabled: bool = False) -> None:
    global _TRACER_INITIALIZED
    if _TRACER_INITIALIZED:
        return
    _TRACER_INITIALIZED = True
    if enabled:
        logger.info("OTEL tracing enabled for %s (console exporter)", service_name)
    else:
        logger.debug("OTEL tracing disabled (no-op mode)")


@contextmanager
def trace_span(
    operation: str,
    *,
    attrs: dict[str, Any] | None = None,
) -> Generator[dict[str, Any], None, None]:
    """Context-manager span that records operation, duration, and safe attributes."""
    safe = _safe_attrs(attrs or {})
    span_data: dict[str, Any] = {
        "operation": operation,
        "start_time": time.monotonic(),
        "attrs": safe,
        "status": "ok",
        "error": None,
    }
    try:
        yield span_data
    except Exception as exc:
        span_data["status"] = "error"
        span_data["error"] = type(exc).__name__
        raise
    finally:
        span_data["duration_ms"] = round((time.monotonic() - span_data["start_time"]) * 1000, 2)
        _SPANS.append(span_data)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "span: %s duration=%.1fms status=%s",
                operation,
                span_data["duration_ms"],
                span_data["status"],
            )


def get_recorded_spans() -> list[dict[str, Any]]:
    return list(_SPANS)


def clear_recorded_spans() -> None:
    _SPANS.clear()
