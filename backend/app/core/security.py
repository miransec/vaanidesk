"""Phase 7 — security middleware: headers, CSRF, rate limiting, request size."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        settings = get_settings()
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "0"
        if settings.app_env == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; frame-ancestors 'none'"
        )
        return response


class CsrfMiddleware(BaseHTTPMiddleware):
    """Origin-based CSRF protection for state-changing requests with cookies."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        settings = get_settings()
        if not settings.csrf_enabled:
            return await call_next(request)

        if request.method in SAFE_METHODS:
            return await call_next(request)

        if "cookie" not in request.headers:
            return await call_next(request)

        origin = request.headers.get("origin")
        if origin:
            allowed = settings.cors_origin_list()
            if origin not in allowed:
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {"code": "csrf_origin_denied", "message": "Origin not allowed"}
                    },
                )

        return await call_next(request)


UPLOAD_PATH_PREFIXES = ("/api/v1/voice/upload", "/api/v1/knowledge/upload")


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies (skips file-upload routes with their own limits)."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in UPLOAD_PATH_PREFIXES):
            return await call_next(request)
        settings = get_settings()
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_body_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {"code": "payload_too_large", "message": "Request body too large"}
                },
            )
        return await call_next(request)
