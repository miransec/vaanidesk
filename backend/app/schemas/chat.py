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


class ConfirmationOut(BaseModel):
    token: str
    action: str
    summary: str
    expires_at: datetime | str


class CitationOut(BaseModel):
    document_title: str
    document_version: int
    section_label: str
    chunk_id: UUID
    source_type: str
    score: float


class WorkflowOut(BaseModel):
    status: str
    detected_language: str | None = None
    script: str | None = None
    intent: str | None = None
    intent_confidence: float | None = None
    selected_tool: str | None = None
    tool_execution_status: str | None = None
    clarification_required: bool = False
    confirmation_required: bool = False
    escalation_required: bool = False
    escalation_reason: str | None = None
    trace_id: UUID | None = None
    confirmation: ConfirmationOut | None = None
    citations: list[CitationOut] = Field(default_factory=list)
    retrieval_strategy: str | None = None
    retrieval_confidence: float | None = None
    evidence_confidence_band: str | None = None
    evidence_confidence_features: dict[str, Any] = Field(default_factory=dict)
    no_answer: bool = False
    no_answer_reason: str | None = None
    retrieval_trace_id: UUID | None = None
    suspicious_evidence: bool = False
    tool_result: dict[str, Any] | None = None


class ChatMessageResponse(BaseModel):
    request_id: str
    conversation_id: UUID
    user_message: MessageOut
    assistant_message: MessageOut
    provider: ProviderMetadata
    workflow: WorkflowOut | None = None


class ConfirmActionRequest(BaseModel):
    confirmation_token: str = Field(min_length=16, max_length=256)
    approved: bool


class ConfirmActionResponse(BaseModel):
    request_id: str
    conversation_id: UUID
    assistant_message: MessageOut
    provider: ProviderMetadata
    workflow: WorkflowOut


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
    demo_key: str | None = None

    model_config = {"from_attributes": True}
