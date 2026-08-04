"""Phase 6 evaluations, alerts, audit log.

Revision ID: 0006_phase6
Revises: 0005_phase5
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_phase6"
down_revision: str | None = "0005_phase5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    eval_run_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "failed",
        name="eval_run_status",
        create_type=False,
    )
    eval_run_status.create(op.get_bind(), checkfirst=True)

    eval_case_verdict = postgresql.ENUM(
        "pass",
        "fail",
        "error",
        "skip",
        name="eval_case_verdict",
        create_type=False,
    )
    eval_case_verdict.create(op.get_bind(), checkfirst=True)

    alert_severity = postgresql.ENUM(
        "info",
        "warning",
        "critical",
        name="alert_severity",
        create_type=False,
    )
    alert_severity.create(op.get_bind(), checkfirst=True)

    alert_event_status = postgresql.ENUM(
        "open",
        "acknowledged",
        "resolved",
        name="alert_event_status",
        create_type=False,
    )
    alert_event_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "evaluation_datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "evaluation_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("case_index", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(32), nullable=False, server_default="en"),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("expected_behavior", sa.Text(), nullable=False),
        sa.Column("expected_intent", sa.String(64), nullable=True),
        sa.Column("expected_tool", sa.String(64), nullable=True),
        sa.Column(
            "security_critical",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("security_expectations", sa.Text(), nullable=True),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_eval_cases_dataset", "evaluation_cases", ["dataset_id"])
    op.create_index("ix_eval_cases_category", "evaluation_cases", ["category"])

    op.create_table(
        "evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dataset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_name", sa.String(200), nullable=False),
        sa.Column("status", eval_run_status, nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(64), nullable=False, server_default="mock"),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("concurrency", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("total_cases", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("passed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("security_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pass_rate", sa.Float(), nullable=True),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "regression_detected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("comparison_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_eval_runs_created", "evaluation_runs", ["created_at"])

    op.create_table(
        "evaluation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evaluation_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("verdict", eval_case_verdict, nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("detected_intent", sa.String(64), nullable=True),
        sa.Column("detected_language", sa.String(32), nullable=True),
        sa.Column("selected_tool", sa.String(64), nullable=True),
        sa.Column("workflow_status", sa.String(32), nullable=True),
        sa.Column(
            "security_violation",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("security_detail", sa.Text(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("response_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_eval_results_run", "evaluation_results", ["run_id"])
    op.create_index("ix_eval_results_verdict", "evaluation_results", ["verdict"])

    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("condition_type", sa.String(64), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("severity", alert_severity, nullable=False, server_default="warning"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alert_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("severity", alert_severity, nullable=False),
        sa.Column("status", alert_event_status, nullable=False, server_default="open"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("measured_value", sa.Float(), nullable=True),
        sa.Column("context", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_alert_events_rule", "alert_events", ["rule_id"])
    op.create_index("ix_alert_events_created", "alert_events", ["created_at"])

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False, server_default="system"),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("safe_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_audit_log_created", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("alert_events")
    op.drop_table("alert_rules")
    op.drop_table("evaluation_results")
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_cases")
    op.drop_table("evaluation_datasets")

    for name in [
        "alert_event_status",
        "alert_severity",
        "eval_case_verdict",
        "eval_run_status",
    ]:
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)
