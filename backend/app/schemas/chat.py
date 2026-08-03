from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    conversation_id: UUID | None = None

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content must not be empty")
        return cleaned


class ProviderMetadata(BaseModel):
    provider: str
    model: str
    is_mock: bool
    language_hint: str | None = None
    disclaimer: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class MessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    request_id: str | None = None
    provider_metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    request_id: str
    conversation_id: UUID
    user_message: MessageOut
    assistant_message: MessageOut
    provider: ProviderMetadata


class ConversationSummary(BaseModel):
    id: UUID
    user_id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: UUID
    user_id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]

    model_config = {"from_attributes": True}


class DemoUserOut(BaseModel):
    id: UUID
    email: str
    display_name: str
    demo_key: str

    model_config = {"from_attributes": True}
