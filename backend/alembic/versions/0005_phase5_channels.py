"""Phase 5 omnichannel schema.

Revision ID: 0005_phase5
Revises: 0004_phase4
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase5"
down_revision: str | None = "0004_phase4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    channel_type = postgresql.ENUM(
        "web", "email", "whatsapp", name="channel_type", create_type=False
    )
    channel_type.create(op.get_bind(), checkfirst=True)

    verification_status = postgresql.ENUM(
        "unverified", "pending", "verified", name="verification_status", create_type=False
    )
    verification_status.create(op.get_bind(), checkfirst=True)

    inbound_event_status = postgresql.ENUM(
        "received",
        "processing",
        "processed",
        "duplicate",
        "rejected",
        "failed",
        name="inbound_event_status",
        create_type=False,
    )
    inbound_event_status.create(op.get_bind(), checkfirst=True)

    outbound_message_status = postgresql.ENUM(
        "queued",
        "sending",
        "sent",
        "delivered",
        "failed",
        "dead_letter",
        name="outbound_message_status",
        create_type=False,
    )
    outbound_message_status.create(op.get_bind(), checkfirst=True)

    outbound_message_type = postgresql.ENUM(
        "text",
        "citation",
        "no_answer",
        "ticket",
        "confirmation_link",
        "escalation",
        name="outbound_message_type",
        create_type=False,
    )
    outbound_message_type.create(op.get_bind(), checkfirst=True)

    attachment_scan_status = postgresql.ENUM(
        "pending", "clean", "rejected", name="attachment_scan_status", create_type=False
    )
    attachment_scan_status.create(op.get_bind(), checkfirst=True)

    handoff_status = postgresql.ENUM(
        "queued", "assigned", "resolved", "abandoned", name="handoff_status", create_type=False
    )
    handoff_status.create(op.get_bind(), checkfirst=True)

    external_confirm_status = postgresql.ENUM(
        "pending",
        "confirmed",
        "expired",
        "denied",
        name="external_confirm_status",
        create_type=False,
    )
    external_confirm_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "channel_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("channel_type", channel_type, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("configuration_reference", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "channel_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "channel_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_sender_id_hash", sa.String(128), nullable=False),
        sa.Column("external_sender_display", sa.String(200), nullable=True),
        sa.Column(
            "verification_status", verification_status, nullable=False, server_default="unverified"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_channel_identities_ext_sender",
        "channel_identities",
        ["channel_connection_id", "external_sender_id_hash"],
    )

    op.create_table(
        "conversation_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_thread_id_hash", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_conv_chan_thread",
        "conversation_channels",
        ["channel_connection_id", "external_thread_id_hash"],
    )

    op.create_table(
        "inbound_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "channel_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("external_event_id", sa.String(256), nullable=False),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", inbound_event_status, nullable=False, server_default="received"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "normalized_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("safe_metadata", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint(
            "channel_connection_id", "external_event_id", name="uq_inbound_event_dedup"
        ),
    )
    op.create_index("ix_inbound_events_status", "inbound_events", ["status"])

    op.create_table(
        "outbound_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "channel_connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recipient_identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message_type", outbound_message_type, nullable=False),
        sa.Column("rendered_content", sa.Text(), nullable=False),
        sa.Column("status", outbound_message_status, nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(256), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_outbound_idempotency"),
    )
    op.create_index("ix_outbound_messages_status", "outbound_messages", ["status"])

    op.create_table(
        "delivery_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "outbound_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outbound_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("provider_status", sa.String(64), nullable=True),
        sa.Column("provider_message_id_hash", sa.String(128), nullable=True),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_delivery_attempts_outbound", "delivery_attempts", ["outbound_message_id"])

    op.create_table(
        "channel_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "inbound_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("inbound_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "outbound_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("outbound_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(128), nullable=False),
        sa.Column("storage_reference", sa.String(500), nullable=False),
        sa.Column("scan_status", attachment_scan_status, nullable=False, server_default="pending"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "identity_link_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(128), unique=True, nullable=False),
        sa.Column(
            "channel_identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "external_confirmation_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_hash", sa.String(128), unique=True, nullable=False),
        sa.Column(
            "channel_identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("channel_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("action_args", postgresql.JSONB(), nullable=True),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("status", external_confirm_status, nullable=False, server_default="pending"),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "human_handoff_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", handoff_status, nullable=False, server_default="queued"),
        sa.Column("assigned_agent_id", sa.String(128), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("human_handoff_queue")
    op.drop_table("external_confirmation_requests")
    op.drop_table("identity_link_challenges")
    op.drop_table("channel_attachments")
    op.drop_table("delivery_attempts")
    op.drop_table("outbound_messages")
    op.drop_table("inbound_events")
    op.drop_table("conversation_channels")
    op.drop_table("channel_identities")
    op.drop_table("channel_connections")

    for name in [
        "external_confirm_status",
        "handoff_status",
        "attachment_scan_status",
        "outbound_message_type",
        "outbound_message_status",
        "inbound_event_status",
        "verification_status",
        "channel_type",
    ]:
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
