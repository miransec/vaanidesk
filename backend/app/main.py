from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import (
    AppError,
    HealthResponse,
    ReadyDependency,
    ReadyResponse,
    app_error_handler,
    http_error_handler,
)
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware
from app.core.redis import check_redis, close_redis
from app.database.session import check_database
from app.observability.logging_filters import install_redaction_filter
from app.observability.metrics import collector
from app.observability.tracing import init_tracing


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    install_redaction_filter()
    init_tracing(
        service_name=settings.app_name,
        enabled=getattr(settings, "otel_enabled", False),
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_error_handler)  # type: ignore[arg-type]

    @app.get("/health", response_model=HealthResponse, tags=["ops"])
    async def health() -> HealthResponse:
        collector.inc("health_checks")
        return HealthResponse(status="ok", service="vaanidesk-backend")

    @app.get("/metrics", tags=["ops"], response_class=PlainTextResponse)
    async def metrics() -> PlainTextResponse:
        return PlainTextResponse(
            content=collector.prometheus_text(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get("/ready", tags=["ops"], response_model=None)
    async def ready() -> ReadyResponse | JSONResponse:
        checks: list[ReadyDependency] = []
        db_ok, db_detail = await check_database()
        checks.append(
            ReadyDependency(
                name="postgresql",
                status="ok" if db_ok else "unavailable",
                detail=None if db_ok else db_detail,
            )
        )
        redis_ok, redis_detail = await check_redis()
        checks.append(
            ReadyDependency(
                name="redis",
                status="ok" if redis_ok else "unavailable",
                detail=None if redis_ok else redis_detail,
            )
        )
        # Phase 1: Postgres is required for readiness; Redis is reported but does not
        # block readiness until security features depend on it (Phase 2+).
        body = ReadyResponse(status="ok" if db_ok else "unavailable", checks=checks)
        if not db_ok:
            return JSONResponse(status_code=503, content=body.model_dump())
        return body

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
