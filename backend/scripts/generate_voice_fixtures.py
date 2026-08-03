#!/usr/bin/env python3
"""Generate tiny deterministic WAV fixtures for Phase 4 voice tests."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path


def _wav_bytes(*, freq: float, seconds: float, sample_rate: int = 8000) -> bytes:
    num_samples = int(sample_rate * seconds)
    pcm = bytearray()
    for i in range(num_samples):
        sample = int(3000 * math.sin(2 * math.pi * freq * i / sample_rate))
        pcm.extend(struct.pack("<h", sample))
    data_size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        data_size,
    )
    return header + bytes(pcm)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


FIXTURES: dict[str, float] = {
    "en": 440.0,
    "hi": 480.0,
    "mr": 520.0,
    "hinglish": 560.0,
    "low_confidence": 600.0,
    "unknown": 640.0,
}


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "sample_data" / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)

    hash_to_fixture: dict[str, str] = {}
    for key, freq in FIXTURES.items():
        seconds = 0.25 + (list(FIXTURES.keys()).index(key) * 0.05)
        payload = _wav_bytes(freq=freq, seconds=seconds)
        path = out_dir / f"{key}.wav"
        path.write_bytes(payload)
        hash_to_fixture[_sha256(payload)] = key

    malformed = out_dir / "malformed.wav"
    malformed.write_bytes(b"NOT-A-VALID-WAV-FILE")

    manifest = {
        "fixtures": list(FIXTURES.keys()),
        "hash_to_fixture": hash_to_fixture,
        "malformed_file": "malformed.wav",
        "note": "Deterministic mock STT maps content hashes to fixture keys.",
    }
    (out_dir / "fixtures.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(FIXTURES)} fixtures + malformed.wav to {out_dir}")


if __name__ == "__main__":
    main()
