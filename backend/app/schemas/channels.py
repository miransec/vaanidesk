"""Phase 5 — Channel schemas for API request/response models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# --- Channel Connections ---


class ChannelConnectionOut(BaseModel):
    id: UUID
    channel_type: str
    display_name: str
    enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChannelConnectionToggle(BaseModel):
    enabled: bool


# --- Identity ---


class ChannelIdentityOut(BaseModel):
    id: UUID
    user_id: UUID | None
    channel_connection_id: UUID
    external_sender_display: str | None
    verification_status: str
    created_at: datetime
    linked_at: datetime | None

    model_config = {"from_attributes": True}


# --- Identity Linking ---


class LinkChallengeCreate(BaseModel):
    channel_identity_id: UUID


class LinkChallengeResponse(BaseModel):
    token: str
    url: str
    expires_in_seconds: int


class LinkCompleteRequest(BaseModel):
    token: str


class LinkCompleteResponse(BaseModel):
    status: str
    identity_id: str


class UnlinkRequest(BaseModel):
    identity_id: UUID


# --- External Confirmation ---


class ExternalConfirmationOut(BaseModel):
    id: UUID
    action: str
    summary: str
    status: str
    expires_at: datetime
    confirmed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExternalConfirmRequest(BaseModel):
    approved: bool = True


# --- Inbound Events ---


class InboundEventOut(BaseModel):
    id: UUID
    channel_connection_id: UUID
    external_event_id: str
    status: str
    received_at: datetime
    processed_at: datetime | None
    error_code: str | None
    safe_metadata: dict[str, object] | None

    model_config = {"from_attributes": True}


# --- Outbound Messages ---


class OutboundMessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    channel_connection_id: UUID
    message_type: str
    rendered_content: str
    status: str
    created_at: datetime
    sent_at: datetime | None
    failed_at: datetime | None

    model_config = {"from_attributes": True}


class RetryOutboundRequest(BaseModel):
    message_ids: list[UUID] = Field(default_factory=list)


# --- Handoff ---


class HandoffQueueItemOut(BaseModel):
    id: UUID
    conversation_id: UUID
    status: str
    assigned_agent_id: str | None
    summary: str
    created_at: datetime

    model_config = {"from_attributes": True}


class HandoffAssignRequest(BaseModel):
    agent_id: str


# --- Simulator ---


class SimulatorEmailEvent(BaseModel):
    from_email: str = "testuser@example.com"
    from_display: str = "Test User"
    subject: str = ""
    text_body: str = ""
    message_id: str | None = None


class SimulatorWhatsAppEvent(BaseModel):
    from_phone: str = "+919876543210"
    display_name: str = "Test User"
    text: str = "Hello from WhatsApp simulator"
    message_id: str | None = None


# --- Attachments ---


class ChannelAttachmentOut(BaseModel):
    id: UUID
    content_type: str
    size_bytes: int
    scan_status: str
    created_at: datetime
    expires_at: datetime | None

    model_config = {"from_attributes": True}
