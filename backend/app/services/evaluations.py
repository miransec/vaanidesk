"""Phase 6 evaluation + alert + audit services — thin router support."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.evals.dataset import DATASET_NAME
from app.evals.runner import (
    export_run_json,
    export_run_markdown,
    run_evaluation,
    seed_dataset,
)
from app.models.evaluations import (
    AlertEvent,
    AlertEventStatus,
    AlertRule,
    AlertSeverity,
    AuditLogEntry,
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
)
from app.observability.metrics import collector

logger = logging.getLogger("vaanidesk.services.evaluations")


async def list_datasets(db: AsyncSession) -> list[EvaluationDataset]:
    result = await db.execute(
        select(EvaluationDataset).order_by(desc(EvaluationDataset.created_at))
    )
    return list(result.scalars().all())


async def get_dataset_cases(db: AsyncSession, dataset_id: UUID) -> list[EvaluationCase]:
    result = await db.execute(
        select(EvaluationCase)
        .where(EvaluationCase.dataset_id == dataset_id)
        .order_by(EvaluationCase.case_index)
    )
    return list(result.scalars().all())


async def seed_evaluation_dataset(db: AsyncSession) -> EvaluationDataset:
    ds = await seed_dataset(db)
    await record_audit(
        db,
        action="dataset_seeded",
        resource_type="evaluation_dataset",
        resource_id=str(ds.id),
        detail=f"Seeded dataset '{ds.name}' with {ds.case_count} cases",
    )
    return ds


async def start_evaluation_run(
    db: AsyncSession,
    *,
    dataset_name: str = DATASET_NAME,
    run_name: str | None = None,
    provider: str = "mock",
    seed: int | None = 42,
    concurrency: int = 1,
    timeout_seconds: int = 60,
    compare_with_previous: bool = True,
) -> EvaluationRun:
    collector.inc("eval_runs")
    run = await run_evaluation(
        db,
        dataset_name=dataset_name,
        run_name=run_name,
        provider=provider,
        seed=seed,
        concurrency=concurrency,
        timeout_seconds=timeout_seconds,
        compare_with_previous=compare_with_previous,
    )
    collector.inc("eval_cases_total", run.total_cases)
    collector.inc("eval_passed", run.passed)
    collector.inc("eval_failed", run.failed)
    if run.security_failures > 0:
        collector.inc("eval_security_failures", run.security_failures)
    return run


async def list_runs(
    db: AsyncSession, *, dataset_id: UUID | None = None, limit: int = 50
) -> list[EvaluationRun]:
    stmt = select(EvaluationRun).order_by(desc(EvaluationRun.created_at)).limit(limit)
    if dataset_id:
        stmt = stmt.where(EvaluationRun.dataset_id == dataset_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_run(db: AsyncSession, run_id: UUID) -> EvaluationRun | None:
    return (
        await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
    ).scalar_one_or_none()


async def get_run_results(db: AsyncSession, run_id: UUID) -> list[EvaluationResult]:
    result = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.run_id == run_id)
        .order_by(EvaluationResult.created_at)
    )
    return list(result.scalars().all())


async def get_run_failed_results(db: AsyncSession, run_id: UUID) -> list[EvaluationResult]:
    from app.models.evaluations import EvalCaseVerdict

    result = await db.execute(
        select(EvaluationResult).where(
            EvaluationResult.run_id == run_id,
            EvaluationResult.verdict != EvalCaseVerdict.PASS,
        )
    )
    return list(result.scalars().all())


async def export_run(db: AsyncSession, run_id: UUID, fmt: str = "json") -> str:
    run = await get_run(db, run_id)
    if run is None:
        return "{}"
    results = await get_run_results(db, run_id)
    if fmt == "markdown":
        return export_run_markdown(run, results)
    return export_run_json(run, results)


async def compare_runs(db: AsyncSession, run_id: UUID) -> dict[str, Any]:
    run = await get_run(db, run_id)
    if run is None:
        return {"error": "run not found"}

    previous = None
    if run.comparison_run_id:
        previous = await get_run(db, run.comparison_run_id)

    delta = None
    if previous and previous.pass_rate is not None and run.pass_rate is not None:
        delta = round(run.pass_rate - previous.pass_rate, 2)

    return {
        "current": {
            "id": str(run.id),
            "pass_rate": run.pass_rate,
            "passed": run.passed,
            "failed": run.failed,
            "security_failures": run.security_failures,
        },
        "previous": {
            "id": str(previous.id) if previous else None,
            "pass_rate": previous.pass_rate if previous else None,
            "passed": previous.passed if previous else None,
            "failed": previous.failed if previous else None,
        }
        if previous
        else None,
        "pass_rate_delta": delta,
        "regression_detected": run.regression_detected,
    }


# ---- Alert Rules ----


async def list_alert_rules(db: AsyncSession) -> list[AlertRule]:
    result = await db.execute(select(AlertRule).order_by(AlertRule.name))
    return list(result.scalars().all())


async def create_alert_rule(
    db: AsyncSession,
    *,
    name: str,
    condition_type: str,
    threshold: float,
    window_seconds: int = 300,
    severity: str = "warning",
    description: str = "",
) -> AlertRule:
    rule = AlertRule(
        id=uuid4(),
        name=name,
        condition_type=condition_type,
        threshold=threshold,
        window_seconds=window_seconds,
        severity=AlertSeverity(severity),
        description=description,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def seed_default_alert_rules(db: AsyncSession) -> list[AlertRule]:
    """Idempotent seed of default alert rules."""
    defaults = [
        (
            "High Error Rate",
            "error_rate",
            0.10,
            300,
            "critical",
            "Fires when error rate exceeds 10% in 5-minute window",
        ),
        (
            "High Latency",
            "latency_p95",
            5000.0,
            300,
            "warning",
            "Fires when P95 latency exceeds 5 seconds",
        ),
        (
            "Provider Failure",
            "provider_failure_rate",
            0.50,
            300,
            "critical",
            "Fires when provider failure rate exceeds 50%",
        ),
        (
            "Repeated Unauthorized",
            "unauthorized_rate",
            5.0,
            60,
            "critical",
            "Fires when unauthorized attempts exceed 5 per minute",
        ),
        (
            "Confirmation Replay",
            "confirmation_replay",
            3.0,
            300,
            "critical",
            "Fires on repeated confirmation replay attempts",
        ),
        (
            "Channel Backlog",
            "channel_outbox_backlog",
            100.0,
            600,
            "warning",
            "Fires when channel outbox backlog exceeds 100 messages",
        ),
        (
            "Eval Security Regression",
            "eval_security_regression",
            1.0,
            0,
            "critical",
            "Fires on any eval security failure",
        ),
        (
            "DB Readiness",
            "db_ready",
            0.0,
            60,
            "critical",
            "Fires when database readiness check fails",
        ),
    ]
    rules = []
    for name, ctype, thresh, window, sev, rule_desc in defaults:
        existing = (
            await db.execute(select(AlertRule).where(AlertRule.name == name))
        ).scalar_one_or_none()
        if existing:
            rules.append(existing)
            continue
        rule = AlertRule(
            id=uuid4(),
            name=name,
            condition_type=ctype,
            threshold=thresh,
            window_seconds=window,
            severity=AlertSeverity(sev),
            description=rule_desc,
        )
        db.add(rule)
        rules.append(rule)
    await db.commit()
    return rules


async def list_alert_events(
    db: AsyncSession, *, limit: int = 100, status: str | None = None
) -> list[AlertEvent]:
    stmt = select(AlertEvent).order_by(desc(AlertEvent.created_at)).limit(limit)
    if status:
        stmt = stmt.where(AlertEvent.status == AlertEventStatus(status))
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def acknowledge_alert(db: AsyncSession, event_id: UUID) -> AlertEvent | None:
    event = (
        await db.execute(select(AlertEvent).where(AlertEvent.id == event_id))
    ).scalar_one_or_none()
    if event is None:
        return None
    event.status = AlertEventStatus.ACKNOWLEDGED
    await db.commit()
    await db.refresh(event)
    return event


async def resolve_alert(db: AsyncSession, event_id: UUID) -> AlertEvent | None:
    event = (
        await db.execute(select(AlertEvent).where(AlertEvent.id == event_id))
    ).scalar_one_or_none()
    if event is None:
        return None
    event.status = AlertEventStatus.RESOLVED
    event.resolved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(event)
    return event


# ---- Audit Log ----


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    actor: str = "system",
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str = "",
    safe_metadata: dict[str, Any] | None = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(
        id=uuid4(),
        action=action,
        actor=actor,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        safe_metadata=safe_metadata,
    )
    db.add(entry)
    await db.commit()
    return entry


async def list_audit_log(
    db: AsyncSession,
    *,
    limit: int = 200,
    action: str | None = None,
    resource_type: str | None = None,
) -> list[AuditLogEntry]:
    stmt = select(AuditLogEntry).order_by(desc(AuditLogEntry.created_at)).limit(limit)
    if action:
        stmt = stmt.where(AuditLogEntry.action == action)
    if resource_type:
        stmt = stmt.where(AuditLogEntry.resource_type == resource_type)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---- Observability aggregates ----


async def get_ops_snapshot(db: AsyncSession) -> dict[str, Any]:
    """Aggregate operational metrics from DB traces + in-memory collector."""
    from app.models import AgentTrace, ToolExecution
    from app.models.channels import InboundEvent, OutboundMessage
    from app.models.knowledge import RetrievalTrace
    from app.models.voice import VoiceTrace

    total_requests = (await db.execute(select(func.count()).select_from(AgentTrace))).scalar_one()
    total_tool_execs = (
        await db.execute(select(func.count()).select_from(ToolExecution))
    ).scalar_one()
    total_retrievals = (
        await db.execute(select(func.count()).select_from(RetrievalTrace))
    ).scalar_one()
    total_voice = (await db.execute(select(func.count()).select_from(VoiceTrace))).scalar_one()
    total_inbound = (await db.execute(select(func.count()).select_from(InboundEvent))).scalar_one()
    total_outbound = (
        await db.execute(select(func.count()).select_from(OutboundMessage))
    ).scalar_one()

    mem = collector.snapshot()

    return {
        "db_aggregates": {
            "agent_traces": int(total_requests),
            "tool_executions": int(total_tool_execs),
            "retrieval_queries": int(total_retrievals),
            "voice_operations": int(total_voice),
            "channel_inbound": int(total_inbound),
            "channel_outbound": int(total_outbound),
        },
        "in_memory": mem,
        "uptime_seconds": collector.uptime_seconds(),
    }
