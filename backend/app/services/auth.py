"""Phase 7 — authentication service: register, login, refresh, logout, sessions."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import HashingError, VerificationError, VerifyMismatchError
from sqlalchemy import delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.auth import AuthAuditEvent, RefreshSession, UserRole
from app.models.entities import User
from app.schemas.auth import (
    PasswordChangeRequest,
    RegisterRequest,
    SessionOut,
    TokenResponse,
    UserProfileOut,
)

logger = logging.getLogger(__name__)


def _rows_affected(result: object) -> int:
    return cast(CursorResult[Any], result).rowcount or 0


_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, type=Type.ID)


def _pepper_password(raw: str) -> str:
    settings = get_settings()
    digest: str = hmac.new(
        settings.password_pepper.encode(), raw.encode(), hashlib.sha256
    ).hexdigest()
    return digest


def hash_password(raw: str) -> str:
    peppered = _pepper_password(raw)
    result: str = _ph.hash(peppered)
    return result


def verify_password(raw: str, hashed: str) -> bool:
    peppered = _pepper_password(raw)
    try:
        ok: bool = _ph.verify(hashed, peppered)
        return ok
    except (VerifyMismatchError, VerificationError, HashingError):
        return False


def _needs_rehash(hashed: str) -> bool:
    result: bool = _ph.check_needs_rehash(hashed)
    return result


def create_access_token(user_id: UUID, role: str) -> tuple[str, int]:
    settings = get_settings()
    expires = timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + expires,
        "jti": uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires.total_seconds())


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AppError(
            code="token_expired", message="Access token has expired", status_code=401
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(
            code="invalid_token", message="Invalid access token", status_code=401
        ) from exc


async def _audit(
    db: AsyncSession,
    *,
    user_id: UUID | None,
    event_type: str,
    ip: str | None = None,
    ua: str | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        AuthAuditEvent(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip,
            user_agent=ua[:512] if ua else None,
            detail=detail,
        )
    )


async def register_user(
    db: AsyncSession,
    payload: RegisterRequest,
    ip: str | None = None,
    ua: str | None = None,
) -> UserProfileOut:
    existing = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError(
            code="email_taken",
            message="An account with this email already exists",
            status_code=409,
        )

    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    await db.flush()
    await _audit(db, user_id=user.id, event_type="register", ip=ip, ua=ua)
    await db.commit()
    await db.refresh(user)
    profile: UserProfileOut = UserProfileOut.model_validate(user)
    return profile


async def login_user(
    db: AsyncSession,
    email: str,
    password: str,
    ip: str | None = None,
    ua: str | None = None,
) -> tuple[TokenResponse, str, datetime]:
    """Returns (token_response, raw_refresh_token, refresh_expires_at)."""
    settings = get_settings()

    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        await _audit(db, user_id=None, event_type="login_failed_unknown_email", ip=ip, ua=ua)
        await db.commit()
        raise AppError(
            code="invalid_credentials", message="Invalid email or password", status_code=401
        )

    if user.is_disabled:
        await _audit(db, user_id=user.id, event_type="login_disabled_account", ip=ip, ua=ua)
        await db.commit()
        raise AppError(code="account_disabled", message="Account is disabled", status_code=403)

    now = datetime.now(UTC)
    if user.locked_until and user.locked_until > now:
        await _audit(db, user_id=user.id, event_type="login_locked", ip=ip, ua=ua)
        await db.commit()
        raise AppError(
            code="account_locked",
            message="Account temporarily locked due to repeated failed logins",
            status_code=429,
        )

    if not user.password_hash or not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.max_failed_login_attempts:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
        await _audit(db, user_id=user.id, event_type="login_failed", ip=ip, ua=ua)
        await db.commit()
        raise AppError(
            code="invalid_credentials", message="Invalid email or password", status_code=401
        )

    if _needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.failed_login_attempts = 0
    user.locked_until = None

    access_token, expires_in = create_access_token(user.id, user.role)

    raw_refresh = create_refresh_token()
    family_id = uuid4()
    refresh_expires = now + timedelta(days=settings.refresh_token_expire_days)
    session = RefreshSession(
        user_id=user.id,
        family_id=family_id,
        token_hash=hash_refresh_token(raw_refresh),
        user_agent=ua[:512] if ua else None,
        ip_address=ip,
        expires_at=refresh_expires,
    )
    db.add(session)
    await _audit(db, user_id=user.id, event_type="login_success", ip=ip, ua=ua)
    await db.commit()

    return (
        TokenResponse(access_token=access_token, expires_in=expires_in),
        raw_refresh,
        refresh_expires,
    )


async def refresh_tokens(
    db: AsyncSession,
    raw_refresh_token: str,
    ip: str | None = None,
    ua: str | None = None,
) -> tuple[TokenResponse, str, datetime]:
    settings = get_settings()
    token_hash = hash_refresh_token(raw_refresh_token)
    now = datetime.now(UTC)

    session = (
        await db.execute(select(RefreshSession).where(RefreshSession.token_hash == token_hash))
    ).scalar_one_or_none()

    if session is None:
        raise AppError(code="invalid_refresh", message="Invalid refresh token", status_code=401)

    if session.is_revoked:
        await db.execute(
            update(RefreshSession)
            .where(RefreshSession.family_id == session.family_id)
            .values(is_revoked=True)
        )
        await _audit(
            db,
            user_id=session.user_id,
            event_type="refresh_reuse_detected",
            ip=ip,
            ua=ua,
            detail=f"family={session.family_id}",
        )
        await db.commit()
        raise AppError(
            code="refresh_reuse",
            message="Refresh token reuse detected — all sessions in this family revoked",
            status_code=401,
        )

    if session.expires_at < now:
        session.is_revoked = True
        await _audit(db, user_id=session.user_id, event_type="refresh_expired", ip=ip, ua=ua)
        await db.commit()
        raise AppError(code="refresh_expired", message="Refresh token expired", status_code=401)

    user = (await db.execute(select(User).where(User.id == session.user_id))).scalar_one_or_none()
    if user is None or user.is_disabled:
        session.is_revoked = True
        await db.commit()
        raise AppError(code="account_unavailable", message="Account unavailable", status_code=401)

    session.is_revoked = True
    session.rotated_at = now

    new_raw_refresh = create_refresh_token()
    refresh_expires = now + timedelta(days=settings.refresh_token_expire_days)
    new_session = RefreshSession(
        user_id=user.id,
        family_id=session.family_id,
        token_hash=hash_refresh_token(new_raw_refresh),
        user_agent=ua[:512] if ua else None,
        ip_address=ip,
        expires_at=refresh_expires,
    )
    db.add(new_session)

    access_token, expires_in = create_access_token(user.id, user.role)
    await _audit(db, user_id=user.id, event_type="token_refresh", ip=ip, ua=ua)
    await db.commit()

    return (
        TokenResponse(access_token=access_token, expires_in=expires_in),
        new_raw_refresh,
        refresh_expires,
    )


async def logout(
    db: AsyncSession,
    user_id: UUID,
    raw_refresh_token: str | None = None,
    ip: str | None = None,
    ua: str | None = None,
) -> None:
    if raw_refresh_token:
        token_hash = hash_refresh_token(raw_refresh_token)
        await db.execute(
            update(RefreshSession)
            .where(RefreshSession.token_hash == token_hash, RefreshSession.user_id == user_id)
            .values(is_revoked=True)
        )
    await _audit(db, user_id=user_id, event_type="logout", ip=ip, ua=ua)
    await db.commit()


async def logout_all(
    db: AsyncSession, user_id: UUID, ip: str | None = None, ua: str | None = None
) -> int:
    result = await db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user_id, RefreshSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    await _audit(db, user_id=user_id, event_type="logout_all", ip=ip, ua=ua)
    await db.commit()
    return _rows_affected(result)


async def change_password(
    db: AsyncSession,
    user: User,
    payload: PasswordChangeRequest,
    ip: str | None = None,
    ua: str | None = None,
) -> None:
    if not user.password_hash or not verify_password(payload.current_password, user.password_hash):
        await _audit(db, user_id=user.id, event_type="password_change_failed", ip=ip, ua=ua)
        await db.commit()
        raise AppError(
            code="invalid_current_password",
            message="Current password is incorrect",
            status_code=400,
        )
    user.password_hash = hash_password(payload.new_password)
    await db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    await _audit(db, user_id=user.id, event_type="password_changed", ip=ip, ua=ua)
    await db.commit()


async def disable_account(
    db: AsyncSession, user_id: UUID, ip: str | None = None, ua: str | None = None
) -> None:
    await db.execute(update(User).where(User.id == user_id).values(is_disabled=True))
    await db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user_id, RefreshSession.is_revoked.is_(False))
        .values(is_revoked=True)
    )
    await _audit(db, user_id=user_id, event_type="account_disabled", ip=ip, ua=ua)
    await db.commit()


async def list_sessions(
    db: AsyncSession, user_id: UUID, current_token_hash: str | None = None
) -> list[SessionOut]:
    now = datetime.now(UTC)
    rows = (
        (
            await db.execute(
                select(RefreshSession)
                .where(
                    RefreshSession.user_id == user_id,
                    RefreshSession.is_revoked.is_(False),
                    RefreshSession.expires_at > now,
                )
                .order_by(RefreshSession.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        SessionOut(
            id=r.id,
            user_agent=r.user_agent,
            ip_address=r.ip_address,
            created_at=r.created_at,
            expires_at=r.expires_at,
            is_current=(r.token_hash == current_token_hash) if current_token_hash else False,
        )
        for r in rows
    ]


async def revoke_session(
    db: AsyncSession,
    user_id: UUID,
    session_id: UUID,
    ip: str | None = None,
    ua: str | None = None,
) -> None:
    result = await db.execute(
        update(RefreshSession)
        .where(
            RefreshSession.id == session_id,
            RefreshSession.user_id == user_id,
            RefreshSession.is_revoked.is_(False),
        )
        .values(is_revoked=True)
    )
    if not _rows_affected(result):
        raise AppError(code="session_not_found", message="Session not found", status_code=404)
    await _audit(
        db,
        user_id=user_id,
        event_type="session_revoked",
        ip=ip,
        ua=ua,
        detail=f"session={session_id}",
    )
    await db.commit()


async def cleanup_expired_sessions(db: AsyncSession) -> int:
    now = datetime.now(UTC)
    result = await db.execute(delete(RefreshSession).where(RefreshSession.expires_at < now))
    await db.commit()
    return _rows_affected(result)


def validate_production_config() -> list[str]:
    """Check that production-critical settings are not placeholder values."""
    settings = get_settings()
    issues: list[str] = []

    if settings.app_env == "production":
        if "change-me" in settings.secret_key.lower() or len(settings.secret_key) < 32:
            issues.append("SECRET_KEY is placeholder or too short for production")
        if "change-me" in settings.jwt_secret_key.lower() or len(settings.jwt_secret_key) < 32:
            issues.append("JWT_SECRET_KEY is placeholder or too short for production")
        if "change-me" in settings.password_pepper.lower() or len(settings.password_pepper) < 16:
            issues.append("PASSWORD_PEPPER is placeholder or too short for production")
        if not settings.secure_cookies:
            issues.append("SECURE_COOKIES must be true in production")
        if settings.debug:
            issues.append("DEBUG must be false in production")
        if "*" in settings.cors_origins:
            issues.append("CORS_ORIGINS must not use wildcard in production")

    return issues
