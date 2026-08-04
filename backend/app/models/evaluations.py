"""Phase 6 evaluation + alert models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class EvalRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EvalCaseVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"
    SKIP = "skip"


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertEventStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    cases: Mapped[list[EvaluationCase]] = relationship(back_populates="dataset")
    runs: Mapped[list[EvaluationRun]] = relationship(back_populates="dataset")


class EvaluationCase(Base):
    __tablename__ = "evaluation_cases"
    __table_args__ = (
        Index("ix_eval_cases_dataset", "dataset_id"),
        Index("ix_eval_cases_category", "category"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_index: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_behavior: Mapped[str] = mapped_column(Text, nullable=False)
    expected_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expected_tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    security_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    security_expectations: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    dataset: Mapped[EvaluationDataset] = relationship(back_populates="cases")
    results: Mapped[list[EvaluationResult]] = relationship(back_populates="case")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (Index("ix_eval_runs_created", "created_at"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    dataset_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[EvalRunStatus] = mapped_column(
        Enum(EvalRunStatus, name="eval_run_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=EvalRunStatus.PENDING,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="mock")
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    total_cases: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    security_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    regression_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comparison_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    dataset: Mapped[EvaluationDataset] = relationship(back_populates="runs")
    results: Mapped[list[EvaluationResult]] = relationship(back_populates="run")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        Index("ix_eval_results_run", "run_id"),
        Index("ix_eval_results_verdict", "verdict"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("evaluation_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    verdict: Mapped[EvalCaseVerdict] = mapped_column(
        Enum(
            EvalCaseVerdict,
            name="eval_case_verdict",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detected_language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    selected_tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workflow_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    security_violation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    security_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    response_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    run: Mapped[EvaluationRun] = relationship(back_populates="results")
    case: Mapped[EvaluationCase] = relationship(back_populates="results")


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    condition_type: Mapped[str] = mapped_column(String(64), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            name="alert_severity",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AlertSeverity.WARNING,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list[AlertEvent]] = relationship(back_populates="rule")


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_events_rule", "rule_id"),
        Index("ix_alert_events_created", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    rule_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="CASCADE"),
        nullable=False,
    )
    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(
            AlertSeverity,
            name="alert_severity",
            values_callable=lambda x: [e.value for e in x],
            create_constraint=False,
        ),
        nullable=False,
    )
    status: Mapped[AlertEventStatus] = mapped_column(
        Enum(
            AlertEventStatus,
            name="alert_event_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AlertEventStatus.OPEN,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    measured_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rule: Mapped[AlertRule] = relationship(back_populates="events")


class AuditLogEntry(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created", "created_at"),
        Index("ix_audit_log_action", "action"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    safe_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
