"""Local filesystem audio storage with safe paths and atomic writes."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.core.errors import AppError


@dataclass(frozen=True)
class StoredAudio:
    storage_reference: str
    content_hash: str
    size_bytes: int
    absolute_path: Path


class AudioStorage(Protocol):
    async def save(
        self,
        *,
        data: bytes,
        extension: str,
        owner_user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> StoredAudio: ...

    async def read(self, storage_reference: str) -> bytes: ...

    async def delete(self, storage_reference: str) -> bool: ...

    async def cleanup_expired(self, *, retention_hours: int) -> int: ...


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_extension(ext: str) -> str:
    cleaned = ext.lower().lstrip(".")
    if cleaned not in {"wav", "mp3", "webm", "m4a", "opus"}:
        raise AppError(
            code="audio_extension_unsupported",
            message=f"Unsupported audio extension: {ext}",
            status_code=400,
        )
    return cleaned


def _resolve_reference(root: Path, storage_reference: str) -> Path:
    if not storage_reference or ".." in storage_reference or storage_reference.startswith("/"):
        raise AppError(
            code="audio_path_invalid",
            message="Invalid storage reference.",
            status_code=400,
        )
    candidate = (root / storage_reference).resolve()
    root_resolved = root.resolve()
    if not str(candidate).startswith(str(root_resolved)):
        raise AppError(
            code="audio_path_traversal",
            message="Storage reference escapes the audio root.",
            status_code=400,
        )
    return candidate


class LocalAudioStorage:
    """Development/local AudioStorage — not production S3."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        *,
        data: bytes,
        extension: str,
        owner_user_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> StoredAudio:
        if not data:
            raise AppError(code="audio_empty", message="Audio payload is empty.", status_code=400)

        ext = _safe_extension(extension)
        content_hash = _sha256(data)
        rel_name = f"{uuid4().hex}.{ext}"
        rel_dir = datetime.now(UTC).strftime("%Y/%m/%d")
        rel_path = f"{rel_dir}/{rel_name}"
        dest = _resolve_reference(self.root, rel_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_name = tempfile.mkstemp(prefix="vd-audio-", dir=dest.parent)
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            tmp_path.write_bytes(data)
            os.replace(tmp_path, dest)
        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

        sidecar = dest.with_suffix(dest.suffix + ".meta.json")
        meta_payload = {
            "owner_user_id": owner_user_id,
            "content_hash": content_hash,
            "size_bytes": len(data),
            "stored_at": datetime.now(UTC).isoformat(),
            **(metadata or {}),
        }
        sidecar.write_text(json.dumps(meta_payload, separators=(",", ":")), encoding="utf-8")

        return StoredAudio(
            storage_reference=rel_path,
            content_hash=content_hash,
            size_bytes=len(data),
            absolute_path=dest,
        )

    async def read(self, storage_reference: str) -> bytes:
        path = _resolve_reference(self.root, storage_reference)
        if not path.is_file():
            raise AppError(
                code="audio_not_found",
                message="Audio file not found.",
                status_code=404,
            )
        return path.read_bytes()

    async def delete(self, storage_reference: str) -> bool:
        path = _resolve_reference(self.root, storage_reference)
        if not path.is_file():
            return False
        path.unlink(missing_ok=True)
        sidecar = path.with_suffix(path.suffix + ".meta.json")
        if sidecar.is_file():
            sidecar.unlink(missing_ok=True)
        return True

    async def cleanup_expired(self, *, retention_hours: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)
        removed = 0
        for path in self.root.rglob("*"):
            if not path.is_file() or path.name.endswith(".meta.json"):
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if mtime < cutoff:
                path.unlink(missing_ok=True)
                sidecar = path.with_suffix(path.suffix + ".meta.json")
                if sidecar.is_file():
                    sidecar.unlink(missing_ok=True)
                removed += 1
        return removed


def get_audio_storage(settings: Settings | None = None) -> AudioStorage:
    cfg = settings or get_settings()
    return LocalAudioStorage(Path(cfg.audio_storage_dir))
