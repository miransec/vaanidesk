from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    WAITING_ON_CUSTOMER = "waiting_on_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketCategory(StrEnum):
    ORDER = "order"
    DELIVERY = "delivery"
    CANCELLATION = "cancellation"
    ACCOUNT = "account"
    OTHER = "other"
    HUMAN_ESCALATION = "human_escalation"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ToolRiskLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ToolExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"
    CONFIRMATION_REQUIRED = "confirmation_required"
    SKIPPED = "skipped"


class WorkflowStatus(StrEnum):
    COMPLETED = "completed"
    CLARIFICATION_REQUIRED = "clarification_required"
    CONFIRMATION_REQUIRED = "confirmation_required"
    ESCALATED = "escalated"
    FAILED = "failed"


class IdempotencyState(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    demo_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    conversations: Mapped[list[Conversation]] = relationship(back_populates="user")
    orders: Mapped[list[Order]] = relationship(back_populates="user")
    support_tickets: Mapped[list[SupportTicket]] = relationship(back_populates="user")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_user_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    sku: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    order_items: Mapped[list[OrderItem]] = relationship(back_populates="product")


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("order_number", name="uq_orders_order_number"),
        Index("ix_orders_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    order_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=OrderStatus.PENDING,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    delivery_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="orders")
    items: Mapped[list[OrderItem]] = relationship(back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (Index("ix_order_items_order", "order_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    order_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(back_populates="order_items")


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    __table_args__ = (
        UniqueConstraint("public_ticket_ref", name="uq_support_tickets_public_ref"),
        Index("ix_support_tickets_user_status", "user_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    public_ticket_ref: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    category: Mapped[TicketCategory] = mapped_column(
        Enum(
            TicketCategory, name="ticket_category", values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TicketStatus.OPEN,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        Enum(
            TicketPriority, name="ticket_priority", values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=TicketPriority.NORMAL,
    )
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="support_tickets")


class AgentTrace(Base):
    __tablename__ = "agent_traces"
    __table_args__ = (Index("ix_agent_traces_request", "request_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    detected_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detected_script: Mapped[str | None] = mapped_column(String(32), nullable=True)
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intent_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    extracted_entities: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    selected_tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    clarification_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    confirmation_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    escalation_required: Mapped[bool] = mapped_column(nullable=False, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_status: Mapped[WorkflowStatus] = mapped_column(
        Enum(
            WorkflowStatus, name="workflow_status", values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
    )
    provider_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (Index("ix_tool_executions_request", "request_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    trace_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agent_traces.id", ondelete="SET NULL"), nullable=True
    )
    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[ToolRiskLevel] = mapped_column(
        Enum(ToolRiskLevel, name="tool_risk_level", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    argument_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    argument_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_status: Mapped[ToolExecutionStatus] = mapped_column(
        Enum(
            ToolExecutionStatus,
            name="tool_execution_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            "user_id",
            "tool_name",
            name="uq_idempotency_key_user_tool",
        ),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    argument_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[IdempotencyState] = mapped_column(
        Enum(
            IdempotencyState,
            name="idempotency_state",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
