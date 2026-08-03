"""Audio upload validation — signature, size, duration heuristics."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.errors import AppError

SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,200}$")

MIME_TO_FORMAT = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/webm": "webm",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/aac": "m4a",
}


@dataclass(frozen=True)
class ValidatedAudio:
    data: bytes
    mime_type: str
    audio_format: str
    duration_ms: int
    size_bytes: int
    sample_rate: int | None
    channels: int | None
    content_hash_source: bytes


def _reject_traversal_filename(filename: str | None) -> str:
    if not filename or not filename.strip():
        return "upload.wav"
    raw = filename.strip()
    if ".." in raw or "/" in raw or "\\" in raw:
        raise AppError(
            code="audio_filename_invalid",
            message="Filename contains unsafe characters or path segments.",
            status_code=400,
        )
    if not SAFE_FILENAME_RE.match(raw):
        raise AppError(
            code="audio_filename_invalid",
            message="Filename contains unsafe characters or path segments.",
            status_code=400,
        )
    return raw


def _detect_format(data: bytes) -> str | None:
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if len(data) >= 3 and data[:3] == b"ID3":
        return "mp3"
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0:
        return "mp3"
    if len(data) >= 4 and data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return "m4a"
    return None


def _parse_wav_duration(data: bytes) -> tuple[int, int | None, int | None]:
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AppError(
            code="audio_malformed",
            message="Invalid WAV header.",
            status_code=400,
        )
    offset = 12
    sample_rate: int | None = None
    channels: int | None = None
    bits_per_sample = 16
    data_size = 0
    while offset + 8 <= len(data):
        chunk_id = data[offset : offset + 4]
        chunk_size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        chunk_data_start = offset + 8
        if chunk_id == b"fmt " and chunk_size >= 16:
            channels = struct.unpack("<H", data[chunk_data_start + 2 : chunk_data_start + 4])[0]
            sample_rate = struct.unpack("<I", data[chunk_data_start + 4 : chunk_data_start + 8])[0]
            bits_per_sample = struct.unpack(
                "<H", data[chunk_data_start + 14 : chunk_data_start + 16]
            )[0]
        elif chunk_id == b"data":
            data_size = chunk_size
            break
        offset = chunk_data_start + chunk_size + (chunk_size % 2)
    if not sample_rate or not channels:
        raise AppError(
            code="audio_malformed", message="WAV missing fmt/data chunks.", status_code=400
        )
    bytes_per_sec = sample_rate * channels * (bits_per_sample // 8)
    duration_ms = int((data_size / bytes_per_sec) * 1000) if bytes_per_sec else 0
    return max(duration_ms, 1), sample_rate, channels


def _estimate_compressed_duration(data: bytes, audio_format: str) -> int:
    bitrates = {"mp3": 128_000, "webm": 96_000, "m4a": 128_000}
    bitrate = bitrates.get(audio_format, 128_000)
    return max(int((len(data) * 8 / bitrate) * 1000), 100)


def validate_audio_upload(
    *,
    data: bytes,
    mime_type: str,
    filename: str | None,
    settings: Settings | None = None,
) -> ValidatedAudio:
    cfg = settings or get_settings()
    safe_name = _reject_traversal_filename(filename)

    if not data:
        raise AppError(code="audio_empty", message="Audio file is empty.", status_code=400)
    if len(data) > cfg.audio_max_size_bytes:
        raise AppError(
            code="audio_too_large",
            message="Audio exceeds maximum allowed size.",
            status_code=413,
            details={"max_bytes": cfg.audio_max_size_bytes},
        )

    detected = _detect_format(data)
    if detected is None:
        raise AppError(
            code="audio_format_unsupported",
            message="Unsupported or unrecognized audio format.",
            status_code=400,
        )

    allowed = {fmt.strip().lower() for fmt in cfg.audio_allowed_formats_list()}
    if detected not in allowed:
        raise AppError(
            code="audio_format_not_allowed",
            message=f"Format '{detected}' is not in the allowed list.",
            status_code=400,
            details={"allowed": sorted(allowed)},
        )

    declared = MIME_TO_FORMAT.get(mime_type.lower())
    if declared is not None and declared != detected:
        raise AppError(
            code="audio_mime_mismatch",
            message="Declared MIME type does not match file signature.",
            status_code=400,
            details={"declared": mime_type, "detected": detected},
        )

    sample_rate: int | None = None
    channels: int | None = None
    if detected == "wav":
        duration_ms, sample_rate, channels = _parse_wav_duration(data)
    else:
        duration_ms = _estimate_compressed_duration(data, detected)

    max_ms = cfg.audio_max_duration_seconds * 1000
    if duration_ms > max_ms:
        raise AppError(
            code="audio_duration_exceeded",
            message="Audio duration exceeds the configured maximum.",
            status_code=400,
            details={"max_seconds": cfg.audio_max_duration_seconds},
        )

    _ = safe_name  # validated; stored separately by caller
    return ValidatedAudio(
        data=data,
        mime_type=mime_type,
        audio_format=detected,
        duration_ms=duration_ms,
        size_bytes=len(data),
        sample_rate=sample_rate,
        channels=channels,
        content_hash_source=data,
    )
