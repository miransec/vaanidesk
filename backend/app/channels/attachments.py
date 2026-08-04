"""Attachment validation and storage."""

from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

BLOCKED_EXTENSIONS = {
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".msi",
    ".scr",
    ".pif",
    ".vbs",
    ".js",
    ".wsh",
    ".wsf",
    ".ps1",
    ".sh",
    ".dll",
}

BLOCKED_MIMES = {
    "application/x-executable",
    "application/x-msdos-program",
    "application/x-msdownload",
    "application/x-sh",
    "application/x-shellscript",
}


def validate_attachment(
    *,
    content_type: str,
    size_bytes: int,
    filename: str | None = None,
) -> None:
    """Validate attachment against size/MIME/extension rules. Raises AppError on rejection."""
    settings = get_settings()
    max_bytes = int(getattr(settings, "channel_attachment_max_bytes", 10_485_760))

    if size_bytes > max_bytes:
        raise AppError(
            code="attachment_too_large",
            message=f"Attachment exceeds maximum size ({max_bytes} bytes).",
            status_code=413,
        )

    if content_type.lower() in BLOCKED_MIMES:
        raise AppError(
            code="attachment_type_blocked",
            message="This file type is not allowed for security reasons.",
            status_code=415,
        )

    if filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in BLOCKED_EXTENSIONS:
            raise AppError(
                code="attachment_extension_blocked",
                message="This file extension is not allowed for security reasons.",
                status_code=415,
            )


def compute_content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_attachment(
    *,
    data: bytes,
    content_hash: str,
    owner_user_id: UUID | None = None,
) -> str:
    """Store attachment data and return storage reference. Mock implementation."""
    return f"mock://attachments/{content_hash[:16]}"


def authorize_download(*, owner_user_id: UUID | None, requesting_user_id: UUID) -> bool:
    """Check if requesting user may access this attachment."""
    if owner_user_id is None:
        return False
    return owner_user_id == requesting_user_id
