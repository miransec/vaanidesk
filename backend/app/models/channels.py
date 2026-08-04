"""Phase 5 — Omnichannel models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- Enums ---


class ChannelType(StrEnum):
    WEB = "web"
    EMAIL = "email"
    WHATSAPP = "whatsapp"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"


class InboundEventStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    FAILED = "failed"


class OutboundMessageStatus(StrEnum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class OutboundMessageType(StrEnum):
    TEXT = "text"
    CITATION = "citation"
    NO_ANSWER = "no_answer"
    TICKET = "ticket"
    CONFIRMATION_LINK = "confirmation_link"
    ESCALATION = "escalation"


class AttachmentScanStatus(StrEnum):
    PENDING = "pending"
    CLEAN = "clean"
    REJECTED = "rejected"


class HandoffStatus(StrEnum):
    QUEUED = "queued"
    ASSIGNED = "assigned"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class ExternalConfirmStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    DENIED = "denied"


# --- Models ---


class ChannelConnection(Base):
    __tablename__ = "channel_connections"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    channel_type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType, name="channel_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    configuration_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ChannelIdentity(Base):
    __tablename__ = "channel_identities"
    __table_args__ = (
        Index(
            "ix_channel_identities_ext_sender", "channel_connection_id", "external_sender_id_hash"
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    channel_connection_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channel_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_sender_id_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    external_sender_display: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            name="verification_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationChannel(Base):
    __tablename__ = "conversation_channels"
    __table_args__ = (
        Index("ix_conv_chan_thread", "channel_connection_id", "external_thread_id_hash"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_connection_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channel_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_identity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channel_identities.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_thread_id_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class InboundEvent(Base):
    __tablename__ = "inbound_events"
    __table_args__ = (
        UniqueConstraint(
            "channel_connection_id", "external_event_id", name="uq_inbound_event_dedup"
        ),
        Index("ix_inbound_events_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    channel_connection_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channel_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_event_id: Mapped[str] = mapped_column(String(256), nullable=False)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[InboundEventStatus] = mapped_column(
        Enum(
            InboundEventStatus,
            name="inbound_event_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=InboundEventStatus.RECEIVED,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalized_message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    safe_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"
    __table_args__ = (
        Index("ix_outbound_messages_status", "status"),
        UniqueConstraint("idempotency_key", name="uq_outbound_idempotency"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_connection_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channel_connections.id", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_identity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channel_identities.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_type: Mapped[OutboundMessageType] = mapped_column(
        Enum(
            OutboundMessageType,
            name="outbound_message_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    rendered_content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[OutboundMessageStatus] = mapped_column(
        Enum(
            OutboundMessageStatus,
            name="outbound_message_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=OutboundMessageStatus.QUEUED,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    __table_args__ = (Index("ix_delivery_attempts_outbound", "outbound_message_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    outbound_message_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("outbound_messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    provider_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_message_id_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelAttachment(Base):
    __tablename__ = "channel_attachments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    inbound_event_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("inbound_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    outbound_message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("outbound_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    scan_status: Mapped[AttachmentScanStatus] = mapped_column(
        Enum(
            AttachmentScanStatus,
            name="attachment_scan_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AttachmentScanStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdentityLinkChallenge(Base):
    __tablename__ = "identity_link_challenges"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    channel_identity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channel_identities.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExternalConfirmationRequest(Base):
    __tablename__ = "external_confirmation_requests"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    channel_identity_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("channel_identities.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    action_args: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ExternalConfirmStatus] = mapped_column(
        Enum(
            ExternalConfirmStatus,
            name="external_confirm_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ExternalConfirmStatus.PENDING,
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class HumanHandoffQueueItem(Base):
    __tablename__ = "human_handoff_queue"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[HandoffStatus] = mapped_column(
        Enum(
            HandoffStatus,
            name="handoff_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=HandoffStatus.QUEUED,
    )
    assigned_agent_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
