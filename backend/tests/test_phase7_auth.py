"""Phase 7 — authentication, security, and production hardening tests."""

from __future__ import annotations

import hashlib
import os
import secrets
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from app.main import create_app
from app.services.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    validate_production_config,
    verify_password,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://vaanidesk:vaanidesk_dev_password@localhost:5432/vaanidesk",
)


async def _db_available() -> bool:
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture
async def require_db() -> AsyncIterator[None]:
    if not await _db_available():
        pytest.skip("PostgreSQL is not available")
    yield


@pytest.fixture
async def client(require_db: None) -> AsyncIterator[AsyncClient]:
    os.environ["DATABASE_URL"] = DATABASE_URL
    os.environ["LLM_PROVIDER"] = "mock"
    from app.core.config import get_settings
    from app.core.redis import reset_redis
    from app.database.session import get_db, reset_engine

    get_settings.cache_clear()
    reset_engine()
    await reset_redis()
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    app = create_app()

    async def _override_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await reset_redis()
    await engine.dispose()
    reset_engine()
    get_settings.cache_clear()


@pytest.fixture
def app():
    return create_app()


# ---------------------------------------------------------------------------
# Password hashing (Argon2id + pepper)
# ---------------------------------------------------------------------------


def test_argon2id_hash_and_verify() -> None:
    raw = "S3cur3P@ssw0rd!"
    hashed = hash_password(raw)
    assert hashed.startswith("$argon2id$")
    assert verify_password(raw, hashed)


def test_argon2id_wrong_password_fails() -> None:
    hashed = hash_password("correct-password")
    assert not verify_password("wrong-password", hashed)


def test_password_pepper_changes_hash() -> None:
    raw = "test-password"
    h1 = hash_password(raw)
    with patch("app.services.auth.get_settings") as mock_settings:
        mock_obj = mock_settings.return_value
        mock_obj.password_pepper = "different-pepper-value!"
        mock_obj.jwt_secret_key = "test"
        mock_obj.jwt_algorithm = "HS256"
        mock_obj.access_token_expire_minutes = 15
        h2 = hash_password(raw)
    assert h1 != h2


# ---------------------------------------------------------------------------
# JWT access token
# ---------------------------------------------------------------------------


def test_create_and_decode_access_token() -> None:
    from uuid import uuid4

    uid = uuid4()
    token, exp = create_access_token(uid, "customer")
    assert exp > 0
    payload = decode_access_token(token)
    assert str(uid) == payload["sub"]
    assert payload["role"] == "customer"


def test_decode_invalid_token_raises() -> None:
    from app.core.errors import AppError

    with pytest.raises(AppError):
        decode_access_token("not.a.real.token")


# ---------------------------------------------------------------------------
# Refresh token hashing
# ---------------------------------------------------------------------------


def test_refresh_token_hash_deterministic() -> None:
    raw = "test-refresh-token-abc123"
    h1 = hash_refresh_token(raw)
    h2 = hash_refresh_token(raw)
    assert h1 == h2
    assert h1 == hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


def test_validate_production_config_dev_passes() -> None:
    issues = validate_production_config()
    assert issues == []


def test_validate_production_config_catches_weak_secrets() -> None:
    with patch("app.services.auth.get_settings") as mock:
        obj = mock.return_value
        obj.app_env = "production"
        obj.secret_key = "change-me"
        obj.jwt_secret_key = "change-me"
        obj.password_pepper = "change-me"
        obj.secure_cookies = False
        obj.debug = True
        obj.cors_origins = "*"
        issues = validate_production_config()
    assert len(issues) >= 5


# ---------------------------------------------------------------------------
# Auth API — registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"test-{unique}@example.com",
            "password": "Str0ngP@ss!",
            "display_name": "Test User",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == f"test-{unique}@example.com"
    assert data["role"] == "customer"
    assert data["is_disabled"] is False


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"dup-{unique}@example.com"
    payload = {
        "email": email,
        "password": "Str0ngP@ss!",
        "display_name": "Dup User",
    }
    await client.post("/api/v1/auth/register", json=payload)
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "email_taken"


# ---------------------------------------------------------------------------
# Auth API — login / refresh / logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_returns_token_and_cookie(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"login-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngP@ss!", "display_name": "Login User"},
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Str0ngP@ss!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0
    assert "refresh_token" in res.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_login_wrong_password_fails(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"wrong-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngP@ss!", "display_name": "W User"},
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "WrongPassword1!"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_bearer_auth_works(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"bearer-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngP@ss!", "display_name": "Bearer User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Str0ngP@ss!"},
    )
    token = login_res.json()["access_token"]
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email


@pytest.mark.asyncio
async def test_demo_header_auth_still_works(client: AsyncClient) -> None:
    res = await client.get(
        "/api/v1/conversations",
        headers={"X-Demo-User-Key": "demo-anya"},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_no_auth_returns_401(client: AsyncClient) -> None:
    res = await client.get("/api/v1/conversations")
    assert res.status_code == 401


# ---------------------------------------------------------------------------
# Refresh token rotation + reuse detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_rotation(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"refresh-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngP@ss!", "display_name": "Refresh User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Str0ngP@ss!"},
    )
    cookies = login_res.cookies
    refresh_res = await client.post("/api/v1/auth/refresh", cookies=cookies)
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()


# ---------------------------------------------------------------------------
# Session listing / revocation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"sess-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngP@ss!", "display_name": "Sess User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Str0ngP@ss!"},
    )
    token = login_res.json()["access_token"]
    cookies = login_res.cookies
    sess_res = await client.get(
        "/api/v1/auth/sessions",
        headers={"Authorization": f"Bearer {token}"},
        cookies=cookies,
    )
    assert sess_res.status_code == 200
    sessions = sess_res.json()
    assert len(sessions) >= 1


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_password_change(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"pwch-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "OldP@ssw0rd!", "display_name": "Pw User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "OldP@ssw0rd!"},
    )
    token = login_res.json()["access_token"]
    change_res = await client.post(
        "/api/v1/auth/password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "OldP@ssw0rd!", "new_password": "NewP@ssw0rd!"},
    )
    assert change_res.status_code == 204


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_headers_present(client: AsyncClient) -> None:
    res = await client.get("/health")
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("x-frame-options") == "DENY"
    assert "strict-origin" in res.headers.get("referrer-policy", "")


# ---------------------------------------------------------------------------
# Brute-force lockout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brute_force_lockout(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"brute-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngP@ss!", "display_name": "Brute User"},
    )
    for _ in range(6):
        await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "WrongPassword!"},
        )
    res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Str0ngP@ss!"},
    )
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "account_locked"


# ---------------------------------------------------------------------------
# Request size limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_oversized_request_rejected(client: AsyncClient) -> None:
    large_body = "x" * (3 * 1024 * 1024)
    res = await client.post(
        "/api/v1/chat/messages",
        content=large_body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(large_body))},
    )
    assert res.status_code == 413


# ---------------------------------------------------------------------------
# Production debug disabled
# ---------------------------------------------------------------------------


def test_docs_hidden_in_production() -> None:
    from app.core.config import Settings, get_settings

    get_settings.cache_clear()
    prod_settings = Settings(debug=False, app_env="production")
    with (
        patch("app.core.config.get_settings", return_value=prod_settings),
        patch("app.main.get_settings", return_value=prod_settings),
    ):
        test_app = create_app()
        assert test_app.docs_url is None
        assert test_app.redoc_url is None
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Insecure cookies rejected in production config validation
# ---------------------------------------------------------------------------


def test_insecure_cookies_flagged_production() -> None:
    with patch("app.services.auth.get_settings") as mock:
        obj = mock.return_value
        obj.app_env = "production"
        obj.secret_key = secrets.token_hex(32)
        obj.jwt_secret_key = secrets.token_hex(32)
        obj.password_pepper = secrets.token_hex(16)
        obj.secure_cookies = False
        obj.debug = False
        obj.cors_origins = "https://app.example.com"
        issues = validate_production_config()
    assert any("SECURE_COOKIES" in i for i in issues)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"logout-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngP@ss!", "display_name": "Logout User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Str0ngP@ss!"},
    )
    token = login_res.json()["access_token"]
    cookies = login_res.cookies
    logout_res = await client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
        cookies=cookies,
    )
    assert logout_res.status_code == 204


@pytest.mark.asyncio
async def test_logout_all(client: AsyncClient) -> None:
    unique = secrets.token_hex(8)
    email = f"logoutall-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngP@ss!", "display_name": "LA User"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Str0ngP@ss!"},
    )
    token = login_res.json()["access_token"]
    res = await client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 204
