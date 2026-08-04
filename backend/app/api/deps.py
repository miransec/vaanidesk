"""Request dependencies — Phase 7: production Bearer auth with demo fallback."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.database.session import get_db
from app.models import User
from app.models.auth import UserRole
from app.services.auth import decode_access_token


async def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def _get_user_from_bearer(db: AsyncSession, authorization: str | None) -> User | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:]
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = (await db.execute(select(User).where(User.id == UUID(user_id)))).scalar_one_or_none()
    if user is None:
        raise AppError(code="user_not_found", message="User not found", status_code=401)
    if user.is_disabled:
        raise AppError(code="account_disabled", message="Account is disabled", status_code=403)
    return user


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


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    x_demo_user_id: UUID | None = Header(default=None, alias="X-Demo-User-Id"),
    x_demo_user_key: str | None = Header(default=None, alias="X-Demo-User-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Unified auth: try Bearer first, fall back to demo headers when DEMO_MODE is on."""
    settings = get_settings()

    user = await _get_user_from_bearer(db, authorization)
    if user is not None:
        return user

    if settings.demo_mode and (x_demo_user_id is not None or x_demo_user_key):
        return await get_demo_user(
            x_demo_user_id=x_demo_user_id,
            x_demo_user_key=x_demo_user_key,
            db=db,
        )

    raise AppError(
        code="authentication_required",
        message="Valid authentication is required",
        status_code=401,
    )


def require_role(*allowed: UserRole):
    """Dependency factory: enforce role at the service boundary."""

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in [r.value for r in allowed]:
            raise AppError(
                code="forbidden",
                message="You do not have permission to access this resource",
                status_code=403,
            )
        return user

    return _check
