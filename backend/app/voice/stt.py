"""Speech-to-text provider interface and deterministic mock."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.core.errors import AppError

MOCK_DISCLAIMER = (
    "Deterministic mock STT — not production speech recognition. "
    "Transcripts are fixture-driven for demos and tests."
)

FAIL_HASH = hashlib.sha256(b"__vd_stt_fail__").hexdigest()
TIMEOUT_HASH = hashlib.sha256(b"__vd_stt_timeout__").hexdigest()

FIXTURE_TRANSCRIPTS: dict[str, tuple[str, str, float]] = {
    "en": (
        "What is the return policy for unused items?",
        "en",
        0.92,
    ),
    "hi": (
        "अप्रयुक्त सामान की वापसी नीति क्या है?",
        "hi",
        0.90,
    ),
    "mr": (
        "वापरले न गेलेले सामानासाठी परतावा धोरण काय आहे?",
        "mr",
        0.89,
    ),
    "hinglish": (
        "mera order abhi tak deliver nahi hua, return policy kya hai?",
        "hinglish",
        0.87,
    ),
    "low_confidence": (
        "maybe return something policy?",
        "en",
        0.35,
    ),
    "unknown": (
        "???",
        "unknown",
        0.20,
    ),
}


@dataclass(frozen=True)
class STTResult:
    transcript: str
    detected_language: str
    confidence: float
    duration_ms: int
    provider: str
    is_mock: bool = True
    disclaimer: str = MOCK_DISCLAIMER
    metadata: dict[str, Any] = field(default_factory=dict)


class SpeechToTextProvider(Protocol):
    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        content_hash: str,
        requested_language: str | None = None,
        fixture_key: str | None = None,
        mock_mode: str | None = None,
    ) -> STTResult: ...


def _load_fixture_manifest() -> dict[str, str]:
    candidates = [
        Path("sample_data/audio/fixtures.json"),
        Path("/sample_data/audio/fixtures.json"),
        Path(__file__).resolve().parents[3] / "sample_data" / "audio" / "fixtures.json",
    ]
    for path in candidates:
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return {str(k): str(v) for k, v in payload.get("hash_to_fixture", {}).items()}
    return {}


class DeterministicMockSTTProvider:
    """Fixture-driven mock STT — clearly labelled, no external credentials."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._hash_map = _load_fixture_manifest()

    def _resolve_fixture(
        self,
        *,
        content_hash: str,
        fixture_key: str | None,
    ) -> str:
        if fixture_key and fixture_key in FIXTURE_TRANSCRIPTS:
            return fixture_key
        mapped = self._hash_map.get(content_hash)
        if mapped:
            return mapped
        # Stable fallback from hash nibble
        keys = list(FIXTURE_TRANSCRIPTS.keys())
        idx = int(content_hash[:2], 16) % len(keys)
        return keys[idx]

    async def transcribe(
        self,
        *,
        audio_bytes: bytes,
        content_hash: str,
        requested_language: str | None = None,
        fixture_key: str | None = None,
        mock_mode: str | None = None,
    ) -> STTResult:
        mode = (mock_mode or "").lower()
        if mode == "timeout" or content_hash == TIMEOUT_HASH:
            await asyncio.sleep(min(self.settings.audio_processing_timeout_seconds, 0.05))
            raise AppError(
                code="stt_timeout",
                message="Mock STT provider timed out.",
                status_code=504,
            )
        if mode == "fail" or content_hash == FAIL_HASH:
            raise AppError(
                code="stt_provider_error",
                message="Mock STT provider simulated failure.",
                status_code=502,
            )

        key = self._resolve_fixture(content_hash=content_hash, fixture_key=fixture_key)
        transcript, detected, confidence = FIXTURE_TRANSCRIPTS[key]
        if requested_language and requested_language in FIXTURE_TRANSCRIPTS:
            transcript, detected, confidence = FIXTURE_TRANSCRIPTS[requested_language]

        duration_ms = max(100, len(audio_bytes) // 32)
        return STTResult(
            transcript=transcript,
            detected_language=detected,
            confidence=confidence,
            duration_ms=duration_ms,
            provider="mock-stt-deterministic",
            metadata={"fixture_key": key, "content_hash_prefix": content_hash[:8]},
        )


def get_stt_provider(settings: Settings | None = None) -> SpeechToTextProvider:
    cfg = settings or get_settings()
    if cfg.stt_provider != "mock":
        raise AppError(
            code="stt_provider_unconfigured",
            message="Only mock STT is implemented in Phase 4.",
            status_code=501,
        )
    return DeterministicMockSTTProvider(cfg)
