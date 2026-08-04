"""Phase 6 evaluation + observability schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationDatasetOut(BaseModel):
    id: UUID
    name: str
    description: str
    version: int
    case_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvaluationCaseOut(BaseModel):
    id: UUID
    dataset_id: UUID
    case_index: int
    language: str
    category: str
    input_text: str
    expected_behavior: str
    expected_intent: str | None = None
    expected_tool: str | None = None
    security_critical: bool = False
    security_expectations: str | None = None

    model_config = {"from_attributes": True}


class EvaluationRunOut(BaseModel):
    id: UUID
    dataset_id: UUID
    run_name: str
    status: str
    provider: str
    seed: int | None = None
    total_cases: int
    passed: int
    failed: int
    errors: int
    skipped: int
    security_failures: int
    pass_rate: float | None = None
    avg_latency_ms: float | None = None
    regression_detected: bool = False
    comparison_run_id: UUID | None = None
    summary: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationResultOut(BaseModel):
    id: UUID
    run_id: UUID
    case_id: UUID
    verdict: str
    latency_ms: int | None = None
    detected_intent: str | None = None
    detected_language: str | None = None
    selected_tool: str | None = None
    workflow_status: str | None = None
    security_violation: bool = False
    security_detail: str | None = None
    score: float | None = None
    response_summary: str | None = None
    error_message: str | None = None
    metrics: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationRunRequest(BaseModel):
    dataset_name: str = "vaanidesk-core-v1"
    run_name: str | None = None
    provider: str = "mock"
    seed: int | None = 42
    concurrency: int = Field(default=1, ge=1, le=16)
    timeout_seconds: int = Field(default=60, ge=5, le=600)
    compare_with_previous: bool = True


class EvaluationRunComparison(BaseModel):
    current_run: EvaluationRunOut
    previous_run: EvaluationRunOut | None = None
    pass_rate_delta: float | None = None
    regression_categories: list[str] = []
    improved_categories: list[str] = []


class AlertRuleOut(BaseModel):
    id: UUID
    name: str
    condition_type: str
    threshold: float
    window_seconds: int
    severity: str
    enabled: bool
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertRuleCreate(BaseModel):
    name: str
    condition_type: str
    threshold: float
    window_seconds: int = 300
    severity: str = "warning"
    description: str = ""


class AlertEventOut(BaseModel):
    id: UUID
    rule_id: UUID
    severity: str
    status: str
    message: str
    measured_value: float | None = None
    context: dict[str, Any] | None = None
    created_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuditLogEntryOut(BaseModel):
    id: UUID
    action: str
    actor: str
    resource_type: str | None = None
    resource_id: str | None = None
    detail: str
    safe_metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MetricsSnapshot(BaseModel):
    """In-memory aggregate metrics for /metrics and admin pages."""

    total_requests: int = 0
    total_errors: int = 0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    active_conversations: int = 0
    tool_executions: int = 0
    tool_errors: int = 0
    retrieval_queries: int = 0
    retrieval_no_answers: int = 0
    voice_operations: int = 0
    voice_errors: int = 0
    channel_inbound: int = 0
    channel_outbound: int = 0
    channel_errors: int = 0
    provider_name: str = "mock"
    uptime_seconds: float = 0.0
