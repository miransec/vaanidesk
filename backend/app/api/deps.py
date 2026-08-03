from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.database.session import get_db
from app.models import User


async def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def get_demo_user(
    x_demo_user_id: UUID | None = Header(default=None, alias="X-Demo-User-Id"),
    x_demo_user_key: str | None = Header(default=None, alias="X-Demo-User-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Phase 1 demo authentication — NOT production-ready.

    Identify the caller with either:
    - X-Demo-User-Id: UUID of a seeded user
    - X-Demo-User-Key: stable demo_key such as demo-anya
    """
    if x_demo_user_id is None and not x_demo_user_key:
        raise AppError(
            code="demo_auth_required",
            message=(
                "Provide X-Demo-User-Id or X-Demo-User-Key. "
                "Phase 1 uses demo authentication only — not production auth."
            ),
            status_code=401,
        )

    stmt = select(User)
    if x_demo_user_id is not None:
        stmt = stmt.where(User.id == x_demo_user_id)
    else:
        assert x_demo_user_key is not None
        stmt = stmt.where(User.demo_key == x_demo_user_key)

    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError(
            code="demo_user_not_found",
            message="Demo user not found. Run the seed script and use a documented demo identity.",
            status_code=401,
        )
    return user
