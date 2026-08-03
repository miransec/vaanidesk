"""Tool definition primitives."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ToolRiskLevel, User


class ToolContext(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    user: User
    request_id: str
    conversation_id: Any = None
    db: Any = None
    idempotency_key: str | None = None


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_model: type[BaseModel]
    risk_level: ToolRiskLevel
    requires_confirmation: bool
    supports_idempotency: bool
    handler: Callable[..., Awaitable[dict[str, Any]]]
    timeout_seconds: float = 10.0

    async def execute(
        self, *, db: AsyncSession, user: User, arguments: dict[str, Any], **kwargs: Any
    ) -> dict[str, Any]:
        payload = self.input_model.model_validate(arguments)
        return await self.handler(db=db, user=user, args=payload, **kwargs)
