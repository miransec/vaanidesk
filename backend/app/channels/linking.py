"""Identity linking — challenge-based link/unlink with single-use tokens."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.channels import (
    ChannelIdentity,
    IdentityLinkChallenge,
    VerificationStatus,
)

logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_link_challenge(
    *,
    db: AsyncSession,
    channel_identity_id: UUID,
    user_id: UUID,
) -> dict[str, str | int]:
    """Create a one-time link challenge token."""
    settings = get_settings()
    ttl = int(getattr(settings, "channel_link_challenge_ttl_seconds", 600))

    token = secrets.token_urlsafe(32)
    challenge = IdentityLinkChallenge(
        id=uuid4(),
        token_hash=_hash_token(token),
        channel_identity_id=channel_identity_id,
        user_id=user_id,
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
    )
    db.add(challenge)
    await db.flush()

    frontend_url = getattr(settings, "frontend_url", "http://localhost:3000")
    link_url = f"{frontend_url}/channels/link?token={token}"

    return {"token": token, "url": link_url, "expires_in_seconds": ttl}


async def complete_link_challenge(
    *,
    db: AsyncSession,
    token: str,
    user_id: UUID,
) -> dict[str, str]:
    """Complete link: verify token, bind identity to user."""
    token_hash = _hash_token(token)
    stmt = select(IdentityLinkChallenge).where(IdentityLinkChallenge.token_hash == token_hash)
    challenge = (await db.execute(stmt)).scalar_one_or_none()

    if challenge is None:
        raise AppError(code="link_token_invalid", message="Link token is invalid.", status_code=400)

    if challenge.user_id != user_id:
        raise AppError(
            code="link_token_forbidden", message="Token not for this user.", status_code=403
        )

    if challenge.used_at is not None:
        raise AppError(code="link_token_used", message="Link token already used.", status_code=400)

    if challenge.expires_at < datetime.now(UTC):
        raise AppError(
            code="link_token_expired", message="Link token has expired.", status_code=400
        )

    challenge.used_at = datetime.now(UTC)

    identity = await db.get(ChannelIdentity, challenge.channel_identity_id)
    if identity is None:
        raise AppError(
            code="identity_not_found", message="Channel identity not found.", status_code=404
        )

    identity.user_id = user_id
    identity.verification_status = VerificationStatus.VERIFIED
    identity.linked_at = datetime.now(UTC)
    await db.flush()

    return {"status": "linked", "identity_id": str(identity.id)}


async def unlink_identity(
    *,
    db: AsyncSession,
    identity_id: UUID,
    user_id: UUID,
) -> dict[str, str]:
    """Unlink identity from user (revoke access)."""
    identity = await db.get(ChannelIdentity, identity_id)
    if identity is None:
        raise AppError(
            code="identity_not_found", message="Channel identity not found.", status_code=404
        )

    if identity.user_id != user_id:
        raise AppError(
            code="identity_forbidden",
            message="Cannot unlink another user's identity.",
            status_code=403,
        )

    identity.user_id = None
    identity.verification_status = VerificationStatus.UNVERIFIED
    identity.linked_at = None
    await db.flush()

    return {"status": "unlinked", "identity_id": str(identity.id)}
