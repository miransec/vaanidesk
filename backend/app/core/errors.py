from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    request_id: str | None = None


class APIError(BaseModel):
    error: ErrorBody


class AppError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = APIError(
        error=ErrorBody(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=request_id,
        )
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code", "http_error"))
        message = str(detail.get("message", detail))
        details = detail.get("details")
    else:
        code = "http_error"
        message = str(detail)
        details = None
    body = APIError(
        error=ErrorBody(code=code, message=message, details=details, request_id=request_id)
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump())


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "vaanidesk-backend"


class ReadyDependency(BaseModel):
    name: str
    status: str
    detail: str | None = None


class ReadyResponse(BaseModel):
    status: str
    checks: list[ReadyDependency] = Field(default_factory=list)
