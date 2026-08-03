"""Typed request/response schemas for Phase 4 voice APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.chat import MessageOut, ProviderMetadata, WorkflowOut


class VoiceProviderOut(BaseModel):
    provider: str
    is_mock: bool = True
    disclaimer: str


class VoiceMessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    user_id: UUID
    message_id: UUID | None = None
    requested_language: str | None = None
    detected_language: str | None = None
    original_filename: str | None = None
    mime_type: str
    audio_format: str
    duration_ms: int | None = None
    size_bytes: int
    content_hash: str
    transcription_status: str
    transcript: str | None = None
    transcript_confidence: float | None = None
    transcript_hash: str | None = None
    transcript_confirmed_at: datetime | None = None
    submitted_at: datetime | None = None
    auto_submitted: bool = False
    requires_transcript_confirmation: bool = False
    can_auto_submit: bool = False
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VoiceUploadResponse(BaseModel):
    request_id: str
    voice_message: VoiceMessageOut
    provider: VoiceProviderOut


class VoiceStatusResponse(BaseModel):
    request_id: str
    voice_message: VoiceMessageOut
    provider: VoiceProviderOut


class TranscriptConfirmRequest(BaseModel):
    transcript_hash: str = Field(min_length=64, max_length=64)


class TranscriptEditRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=8000)


class VoiceSubmitResponse(BaseModel):
    request_id: str
    voice_message: VoiceMessageOut
    conversation_id: UUID
    user_message: MessageOut | None = None
    assistant_message: MessageOut | None = None
    provider: ProviderMetadata
    workflow: WorkflowOut | None = None


class TTSRequest(BaseModel):
    message_id: UUID
    language: str | None = None
    voice_name: str | None = None


class SpeechSynthesisOut(BaseModel):
    id: UUID
    message_id: UUID
    user_id: UUID
    language: str
    provider: str
    voice_name: str | None = None
    audio_format: str
    duration_ms: int | None = None
    size_bytes: int | None = None
    content_hash: str | None = None
    status: str
    download_url: str | None = None
    expires_at: datetime | None = None
    is_mock: bool = True
    disclaimer: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VoiceDeleteResponse(BaseModel):
    request_id: str
    deleted: bool
    voice_message_id: UUID


class VoiceCleanupResponse(BaseModel):
    request_id: str
    removed_files: int


class VoiceTranscribeQuery(BaseModel):
    mock_mode: Literal["fail", "timeout"] | None = None
    fixture_key: str | None = None
