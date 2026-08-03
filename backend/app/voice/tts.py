"""Text-to-speech provider interface and deterministic mock WAV generator."""

from __future__ import annotations

import asyncio
import hashlib
import math
import struct
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import Settings, get_settings
from app.core.errors import AppError

MOCK_TTS_DISCLAIMER = "Deterministic mock TTS — synthetic waveform, not natural speech quality."


@dataclass(frozen=True)
class TTSResult:
    audio_bytes: bytes
    content_hash: str
    duration_ms: int
    provider: str
    audio_format: str = "wav"
    is_mock: bool = True
    disclaimer: str = MOCK_TTS_DISCLAIMER
    metadata: dict[str, Any] = field(default_factory=dict)


class TextToSpeechProvider(Protocol):
    async def synthesize(
        self,
        *,
        text: str,
        language: str,
        voice_name: str | None = None,
        mock_mode: str | None = None,
    ) -> TTSResult: ...


def _build_deterministic_wav(text: str) -> tuple[bytes, int]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    sample_rate = 8000
    num_samples = 800 + (digest[0] % 1200)
    amplitude = 2000 + (digest[1] * 8)
    freq = 220 + (digest[2] % 180)

    pcm = bytearray()
    for i in range(num_samples):
        sample = int(amplitude * math.sin(2 * math.pi * freq * i / sample_rate))
        pcm.extend(struct.pack("<h", sample))

    data_size = len(pcm)
    byte_rate = sample_rate * 2
    block_align = 2
    riff_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        riff_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        byte_rate,
        block_align,
        16,
        b"data",
        data_size,
    )
    wav = header + bytes(pcm)
    duration_ms = int(num_samples / sample_rate * 1000)
    return wav, duration_ms


class DeterministicMockTTSProvider:
    """Generates minimal valid PCM WAV from text hash — labelled mock."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def synthesize(
        self,
        *,
        text: str,
        language: str,
        voice_name: str | None = None,
        mock_mode: str | None = None,
    ) -> TTSResult:
        mode = (mock_mode or "").lower()
        if mode == "timeout":
            await asyncio.sleep(min(self.settings.audio_processing_timeout_seconds, 0.05))
            raise AppError(
                code="tts_timeout",
                message="Mock TTS provider timed out.",
                status_code=504,
            )
        if mode == "fail":
            raise AppError(
                code="tts_provider_error",
                message="Mock TTS provider simulated failure.",
                status_code=502,
            )
        if not text.strip():
            raise AppError(
                code="tts_text_empty",
                message="Cannot synthesize empty text.",
                status_code=400,
            )

        payload = f"{language}:{voice_name or 'default'}:{text.strip()}"
        audio_bytes, duration_ms = _build_deterministic_wav(payload)
        content_hash = hashlib.sha256(audio_bytes).hexdigest()
        return TTSResult(
            audio_bytes=audio_bytes,
            content_hash=content_hash,
            duration_ms=duration_ms,
            provider="mock-tts-deterministic",
            metadata={"language": language, "voice_name": voice_name or "default"},
        )


def get_tts_provider(settings: Settings | None = None) -> TextToSpeechProvider:
    cfg = settings or get_settings()
    if cfg.tts_provider != "mock":
        raise AppError(
            code="tts_provider_unconfigured",
            message="Only mock TTS is implemented in Phase 4.",
            status_code=501,
        )
    return DeterministicMockTTSProvider(cfg)
