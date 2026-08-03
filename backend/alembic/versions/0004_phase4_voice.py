"""Phase 4 voice schema.

Revision ID: 0004_phase4
Revises: 0003_phase3
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase4"
down_revision: str | None = "0003_phase3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    transcription_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        "confirmed",
        name="voice_transcription_status",
        create_type=True,
    )
    synthesis_status = postgresql.ENUM(
        "pending",
        "processing",
        "completed",
        "failed",
        "expired",
        name="speech_synthesis_status",
        create_type=True,
    )
    trace_operation = postgresql.ENUM(
        "upload",
        "transcribe",
        "confirm",
        "edit",
        "submit",
        "tts",
        "download",
        "delete",
        "cleanup",
        name="voice_trace_operation",
        create_type=True,
    )
    trace_result = postgresql.ENUM(
        "success",
        "failure",
        "timeout",
        name="voice_trace_result_status",
        create_type=True,
    )
    for enum_type in (transcription_status, synthesis_status, trace_operation, trace_result):
        enum_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "voice_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requested_language", sa.String(32), nullable=True),
        sa.Column("detected_language", sa.String(32), nullable=True),
        sa.Column("original_filename", sa.String(260), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("audio_format", sa.String(16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("storage_reference", sa.String(512), nullable=False),
        sa.Column(
            "transcription_status",
            postgresql.ENUM(
                "pending",
                "processing",
                "completed",
                "failed",
                "confirmed",
                name="voice_transcription_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("transcript_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("transcript_hash", sa.String(64), nullable=True),
        sa.Column("transcript_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_submitted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_voice_messages_user_created", "voice_messages", ["user_id", "created_at"])
    op.create_index(
        "ix_voice_messages_conversation", "voice_messages", ["conversation_id", "created_at"]
    )
    op.create_index("ix_voice_messages_content_hash", "voice_messages", ["content_hash"])

    op.create_table(
        "speech_syntheses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("voice_name", sa.String(64), nullable=True),
        sa.Column("audio_format", sa.String(16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("storage_reference", sa.String(512), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "pending",
                "processing",
                "completed",
                "failed",
                "expired",
                name="speech_synthesis_status",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_speech_syntheses_user_created", "speech_syntheses", ["user_id", "created_at"]
    )
    op.create_index("ix_speech_syntheses_message", "speech_syntheses", ["message_id"])

    op.create_table(
        "voice_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column(
            "voice_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "operation",
            postgresql.ENUM(
                "upload",
                "transcribe",
                "confirm",
                "edit",
                "submit",
                "tts",
                "download",
                "delete",
                "cleanup",
                name="voice_trace_operation",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("language", sa.String(32), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "result_status",
            postgresql.ENUM(
                "success",
                "failure",
                "timeout",
                name="voice_trace_result_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("safe_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_voice_traces_request", "voice_traces", ["request_id"])
    op.create_index("ix_voice_traces_user_created", "voice_traces", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_voice_traces_user_created", table_name="voice_traces")
    op.drop_index("ix_voice_traces_request", table_name="voice_traces")
    op.drop_table("voice_traces")

    op.drop_index("ix_speech_syntheses_message", table_name="speech_syntheses")
    op.drop_index("ix_speech_syntheses_user_created", table_name="speech_syntheses")
    op.drop_table("speech_syntheses")

    op.drop_index("ix_voice_messages_content_hash", table_name="voice_messages")
    op.drop_index("ix_voice_messages_conversation", table_name="voice_messages")
    op.drop_index("ix_voice_messages_user_created", table_name="voice_messages")
    op.drop_table("voice_messages")

    bind = op.get_bind()
    for name in (
        "voice_trace_result_status",
        "voice_trace_operation",
        "speech_synthesis_status",
        "voice_transcription_status",
    ):
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
