"""Workflow result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.models import WorkflowStatus


@dataclass
class ConfirmationView:
    token: str
    action: str
    summary: str
    expires_at: str


@dataclass
class WorkflowResult:
    status: WorkflowStatus
    assistant_text: str
    language_code: str
    script: str
    intent: str | None
    intent_confidence: float | None
    selected_tool: str | None = None
    tool_execution_status: str | None = None
    clarification_required: bool = False
    confirmation_required: bool = False
    escalation_required: bool = False
    escalation_reason: str | None = None
    trace_id: UUID | None = None
    confirmation: ConfirmationView | None = None
    tool_result: dict[str, Any] | None = None
    entities: dict[str, Any] = field(default_factory=dict)
    provider_name: str = "workflow-heuristic"
    latency_ms: int | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    retrieval_strategy: str | None = None
    retrieval_confidence: float | None = None
    evidence_confidence_band: str | None = None
    evidence_confidence_features: dict[str, Any] = field(default_factory=dict)
    no_answer: bool = False
    no_answer_reason: str | None = None
    retrieval_trace_id: UUID | None = None
    suspicious_evidence: bool = False
