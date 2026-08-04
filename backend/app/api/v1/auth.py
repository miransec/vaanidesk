"""Phase 7 — authentication API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.database.session import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    SessionOut,
    TokenResponse,
    UserProfileOut,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _set_refresh_cookie(response: Response, token: str, max_age: int) -> None:
    settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        max_age=max_age,
        path=f"{settings.api_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        path=f"{settings.api_prefix}/auth",
    )


@router.post("/register", response_model=UserProfileOut, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserProfileOut:
    return await auth_service.register_user(
        db, payload, ip=_client_ip(request), ua=request.headers.get("user-agent")
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    token_resp, raw_refresh, refresh_expires = await auth_service.login_user(
        db,
        payload.email,
        payload.password,
        ip=_client_ip(request),
        ua=request.headers.get("user-agent"),
    )
    settings = get_settings()
    max_age = settings.refresh_token_expire_days * 86400
    _set_refresh_cookie(response, raw_refresh, max_age)
    return token_resp


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
) -> TokenResponse:
    if not refresh_token:
        from app.core.errors import AppError

        raise AppError(
            code="missing_refresh_token",
            message="Refresh token cookie is missing",
            status_code=401,
        )
    token_resp, new_raw_refresh, refresh_expires = await auth_service.refresh_tokens(
        db,
        refresh_token,
        ip=_client_ip(request),
        ua=request.headers.get("user-agent"),
    )
    settings = get_settings()
    max_age = settings.refresh_token_expire_days * 86400
    _set_refresh_cookie(response, new_raw_refresh, max_age)
    return token_resp


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None),
) -> None:
    await auth_service.logout(
        db,
        user.id,
        refresh_token,
        ip=_client_ip(request),
        ua=request.headers.get("user-agent"),
    )
    _clear_refresh_cookie(response)


@router.post("/logout-all", status_code=204)
async def logout_all(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    await auth_service.logout_all(
        db,
        user.id,
        ip=_client_ip(request),
        ua=request.headers.get("user-agent"),
    )
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserProfileOut)
async def me(user: User = Depends(get_current_user)) -> UserProfileOut:
    return UserProfileOut.model_validate(user)


@router.post("/password", status_code=204)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    await auth_service.change_password(
        db,
        user,
        payload,
        ip=_client_ip(request),
        ua=request.headers.get("user-agent"),
    )
    _clear_refresh_cookie(response)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None),
) -> list[SessionOut]:
    current_hash = None
    if refresh_token:
        current_hash = auth_service.hash_refresh_token(refresh_token)
    return await auth_service.list_sessions(db, user.id, current_hash)


@router.delete("/sessions/{session_id}", status_code=204)
async def revoke_session(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    await auth_service.revoke_session(
        db,
        user.id,
        session_id,
        ip=_client_ip(request),
        ua=request.headers.get("user-agent"),
    )
