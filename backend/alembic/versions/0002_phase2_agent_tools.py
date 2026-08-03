"""Phase 2 agent/tools schema.

Revision ID: 0002_phase2
Revises: 0001_phase1
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase2"
down_revision: str | None = "0001_phase1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("delivery_address", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE orders
        SET delivery_address = 'Demo Address ' || order_number || ', Mumbai, MH 400001'
        WHERE delivery_address IS NULL AND order_number ~ '^[0-9]+$'
        """
    )
    op.execute(
        """
        UPDATE orders
        SET order_number = 'VD-' || (10001 + (order_number::integer - 8300))::text
        WHERE order_number ~ '^[0-9]+$'
        """
    )

    ticket_category = postgresql.ENUM(
        "order",
        "delivery",
        "cancellation",
        "account",
        "other",
        "human_escalation",
        name="ticket_category",
        create_type=True,
    )
    ticket_status = postgresql.ENUM(
        "open",
        "in_progress",
        "waiting_on_customer",
        "resolved",
        "closed",
        name="ticket_status",
        create_type=True,
    )
    ticket_priority = postgresql.ENUM(
        "low", "normal", "high", "urgent", name="ticket_priority", create_type=True
    )
    tool_risk = postgresql.ENUM("low", "moderate", "high", name="tool_risk_level", create_type=True)
    tool_exec_status = postgresql.ENUM(
        "success",
        "failed",
        "rejected",
        "confirmation_required",
        "skipped",
        name="tool_execution_status",
        create_type=True,
    )
    workflow_status = postgresql.ENUM(
        "completed",
        "clarification_required",
        "confirmation_required",
        "escalated",
        "failed",
        name="workflow_status",
        create_type=True,
    )
    idem_state = postgresql.ENUM(
        "in_progress", "completed", "failed", name="idempotency_state", create_type=True
    )
    for e in (
        ticket_category,
        ticket_status,
        ticket_priority,
        tool_risk,
        tool_exec_status,
        workflow_status,
        idem_state,
    ):
        e.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("public_ticket_ref", sa.String(32), nullable=False),
        sa.Column(
            "category",
            postgresql.ENUM(
                "order",
                "delivery",
                "cancellation",
                "account",
                "other",
                "human_escalation",
                name="ticket_category",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "open",
                "in_progress",
                "waiting_on_customer",
                "resolved",
                "closed",
                name="ticket_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            postgresql.ENUM(
                "low", "normal", "high", "urgent", name="ticket_priority", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("public_ticket_ref", name="uq_support_tickets_public_ref"),
    )
    op.create_index(
        "ix_support_tickets_public_ticket_ref", "support_tickets", ["public_ticket_ref"]
    )
    op.create_index("ix_support_tickets_user_status", "support_tickets", ["user_id", "status"])

    op.create_table(
        "agent_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detected_language", sa.String(32), nullable=True),
        sa.Column("detected_script", sa.String(32), nullable=True),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("intent_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("extracted_entities", postgresql.JSONB(), nullable=True),
        sa.Column("selected_tool", sa.String(64), nullable=True),
        sa.Column("risk_level", sa.String(16), nullable=True),
        sa.Column("clarification_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("escalation_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column(
            "workflow_status",
            postgresql.ENUM(
                "completed",
                "clarification_required",
                "confirmation_required",
                "escalated",
                "failed",
                name="workflow_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("provider_name", sa.String(64), nullable=True),
        sa.Column("total_latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_agent_traces_request", "agent_traces", ["request_id"])

    op.create_table(
        "tool_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("trace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column(
            "risk_level",
            postgresql.ENUM("low", "moderate", "high", name="tool_risk_level", create_type=False),
            nullable=False,
        ),
        sa.Column("argument_summary", postgresql.JSONB(), nullable=True),
        sa.Column("argument_hash", sa.String(64), nullable=True),
        sa.Column(
            "execution_status",
            postgresql.ENUM(
                "success",
                "failed",
                "rejected",
                "confirmation_required",
                "skipped",
                name="tool_execution_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["trace_id"], ["agent_traces.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_tool_executions_request", "tool_executions", ["request_id"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("argument_hash", sa.String(64), nullable=False),
        sa.Column(
            "state",
            postgresql.ENUM(
                "in_progress", "completed", "failed", name="idempotency_state", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_result", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "idempotency_key", "user_id", "tool_name", name="uq_idempotency_key_user_tool"
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("ix_tool_executions_request", table_name="tool_executions")
    op.drop_table("tool_executions")
    op.drop_index("ix_agent_traces_request", table_name="agent_traces")
    op.drop_table("agent_traces")
    op.drop_index("ix_support_tickets_user_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_public_ticket_ref", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_column("orders", "delivery_address")
    op.execute(
        """
        UPDATE orders
        SET order_number = (8300 + (REPLACE(order_number, 'VD-', '')::integer - 10001))::text
        WHERE order_number LIKE 'VD-%'
        """
    )
    for name in (
        "idempotency_state",
        "workflow_status",
        "tool_execution_status",
        "tool_risk_level",
        "ticket_priority",
        "ticket_status",
        "ticket_category",
    ):
        op.execute(f"DROP TYPE IF EXISTS {name}")
