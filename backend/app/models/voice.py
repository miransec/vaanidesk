"""Phase 4 voice models — audio transport into the controlled orchestrator."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class VoiceTranscriptionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFIRMED = "confirmed"


class SpeechSynthesisStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class VoiceTraceOperation(StrEnum):
    UPLOAD = "upload"
    TRANSCRIBE = "transcribe"
    CONFIRM = "confirm"
    EDIT = "edit"
    SUBMIT = "submit"
    TTS = "tts"
    DOWNLOAD = "download"
    DELETE = "delete"
    CLEANUP = "cleanup"


class VoiceTraceResultStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"


class VoiceMessage(Base):
    __tablename__ = "voice_messages"
    __table_args__ = (
        Index("ix_voice_messages_user_created", "user_id", "created_at"),
        Index("ix_voice_messages_conversation", "conversation_id", "created_at"),
        Index("ix_voice_messages_content_hash", "content_hash"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(260), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    audio_format: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    transcription_status: Mapped[VoiceTranscriptionStatus] = mapped_column(
        Enum(
            VoiceTranscriptionStatus,
            name="voice_transcription_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=VoiceTranscriptionStatus.PENDING,
    )
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    transcript_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    transcript_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    auto_submitted: Mapped[bool] = mapped_column(nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    conversation: Mapped[Any] = relationship("Conversation", foreign_keys=[conversation_id])
    user: Mapped[Any] = relationship("User", foreign_keys=[user_id])
    linked_message: Mapped[Any | None] = relationship("Message", foreign_keys=[message_id])


class SpeechSynthesis(Base):
    __tablename__ = "speech_syntheses"
    __table_args__ = (
        Index("ix_speech_syntheses_user_created", "user_id", "created_at"),
        Index("ix_speech_syntheses_message", "message_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    voice_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    audio_format: Mapped[str] = mapped_column(String(16), nullable=False, default="wav")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    storage_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[SpeechSynthesisStatus] = mapped_column(
        Enum(
            SpeechSynthesisStatus,
            name="speech_synthesis_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=SpeechSynthesisStatus.PENDING,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    message: Mapped[Any] = relationship("Message", foreign_keys=[message_id])
    user: Mapped[Any] = relationship("User", foreign_keys=[user_id])


class VoiceTrace(Base):
    __tablename__ = "voice_traces"
    __table_args__ = (
        Index("ix_voice_traces_request", "request_id"),
        Index("ix_voice_traces_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    voice_message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[VoiceTraceOperation] = mapped_column(
        Enum(
            VoiceTraceOperation,
            name="voice_trace_operation",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    result_status: Mapped[VoiceTraceResultStatus] = mapped_column(
        Enum(
            VoiceTraceResultStatus,
            name="voice_trace_result_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    safe_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
