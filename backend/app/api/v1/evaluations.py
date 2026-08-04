"""Phase 6 evaluation + observability + admin API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models import User
from app.observability.metrics import collector
from app.schemas.evaluations import (
    AlertEventOut,
    AlertRuleCreate,
    AlertRuleOut,
    AuditLogEntryOut,
    EvaluationCaseOut,
    EvaluationDatasetOut,
    EvaluationResultOut,
    EvaluationRunOut,
    EvaluationRunRequest,
)
from app.services import evaluations as eval_service

router = APIRouter(tags=["evaluations"])


# ---- Datasets ----


@router.get("/evaluations/datasets", response_model=list[EvaluationDatasetOut])
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[EvaluationDatasetOut]:
    datasets = await eval_service.list_datasets(db)
    return [EvaluationDatasetOut.model_validate(d) for d in datasets]


@router.get("/evaluations/datasets/{dataset_id}/cases", response_model=list[EvaluationCaseOut])
async def list_dataset_cases(
    dataset_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[EvaluationCaseOut]:
    cases = await eval_service.get_dataset_cases(db, dataset_id)
    return [EvaluationCaseOut.model_validate(c) for c in cases]


@router.post("/evaluations/datasets/seed", response_model=EvaluationDatasetOut)
async def seed_dataset(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> EvaluationDatasetOut:
    ds = await eval_service.seed_evaluation_dataset(db)
    return EvaluationDatasetOut.model_validate(ds)


# ---- Runs ----


@router.post("/evaluations/runs", response_model=EvaluationRunOut)
async def start_run(
    req: EvaluationRunRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> EvaluationRunOut:
    run = await eval_service.start_evaluation_run(
        db,
        dataset_name=req.dataset_name,
        run_name=req.run_name,
        provider=req.provider,
        seed=req.seed,
        concurrency=req.concurrency,
        timeout_seconds=req.timeout_seconds,
        compare_with_previous=req.compare_with_previous,
    )
    return EvaluationRunOut.model_validate(run)


@router.get("/evaluations/runs", response_model=list[EvaluationRunOut])
async def list_runs(
    dataset_id: UUID | None = None,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[EvaluationRunOut]:
    runs = await eval_service.list_runs(db, dataset_id=dataset_id, limit=limit)
    return [EvaluationRunOut.model_validate(r) for r in runs]


@router.get("/evaluations/runs/{run_id}", response_model=EvaluationRunOut)
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> EvaluationRunOut:
    run = await eval_service.get_run(db, run_id)
    if run is None:
        from app.core.errors import AppError

        raise AppError(code="not_found", message="Run not found", status_code=404)
    return EvaluationRunOut.model_validate(run)


@router.get("/evaluations/runs/{run_id}/results", response_model=list[EvaluationResultOut])
async def get_run_results(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[EvaluationResultOut]:
    results = await eval_service.get_run_results(db, run_id)
    return [EvaluationResultOut.model_validate(r) for r in results]


@router.get("/evaluations/runs/{run_id}/failed", response_model=list[EvaluationResultOut])
async def get_run_failures(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[EvaluationResultOut]:
    results = await eval_service.get_run_failed_results(db, run_id)
    return [EvaluationResultOut.model_validate(r) for r in results]


@router.get("/evaluations/runs/{run_id}/export")
async def export_run(
    run_id: UUID,
    fmt: str = Query(default="json", regex="^(json|markdown)$"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PlainTextResponse:
    content = await eval_service.export_run(db, run_id, fmt=fmt)
    media = "application/json" if fmt == "json" else "text/markdown"
    return PlainTextResponse(content=content, media_type=media)


@router.get("/evaluations/runs/{run_id}/compare")
async def compare_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, object]:
    return await eval_service.compare_runs(db, run_id)


# ---- Alert Rules ----


@router.get("/alerts/rules", response_model=list[AlertRuleOut])
async def list_alert_rules(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[AlertRuleOut]:
    rules = await eval_service.list_alert_rules(db)
    return [AlertRuleOut.model_validate(r) for r in rules]


@router.post("/alerts/rules", response_model=AlertRuleOut)
async def create_alert_rule(
    req: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> AlertRuleOut:
    rule = await eval_service.create_alert_rule(
        db,
        name=req.name,
        condition_type=req.condition_type,
        threshold=req.threshold,
        window_seconds=req.window_seconds,
        severity=req.severity,
        description=req.description,
    )
    return AlertRuleOut.model_validate(rule)


@router.post("/alerts/rules/seed")
async def seed_alert_rules(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, int]:
    rules = await eval_service.seed_default_alert_rules(db)
    return {"seeded": len(rules)}


@router.get("/alerts/events", response_model=list[AlertEventOut])
async def list_alert_events(
    limit: int = Query(default=100, le=500),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[AlertEventOut]:
    events = await eval_service.list_alert_events(db, limit=limit, status=status)
    return [AlertEventOut.model_validate(e) for e in events]


@router.post("/alerts/events/{event_id}/acknowledge", response_model=AlertEventOut)
async def acknowledge_alert(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> AlertEventOut:
    event = await eval_service.acknowledge_alert(db, event_id)
    if event is None:
        from app.core.errors import AppError

        raise AppError(code="not_found", message="Alert event not found", status_code=404)
    return AlertEventOut.model_validate(event)


@router.post("/alerts/events/{event_id}/resolve", response_model=AlertEventOut)
async def resolve_alert(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> AlertEventOut:
    event = await eval_service.resolve_alert(db, event_id)
    if event is None:
        from app.core.errors import AppError

        raise AppError(code="not_found", message="Alert event not found", status_code=404)
    return AlertEventOut.model_validate(event)


# ---- Audit Log ----


@router.get("/audit", response_model=list[AuditLogEntryOut])
async def list_audit_log(
    limit: int = Query(default=200, le=1000),
    action: str | None = None,
    resource_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[AuditLogEntryOut]:
    entries = await eval_service.list_audit_log(
        db, limit=limit, action=action, resource_type=resource_type
    )
    return [AuditLogEntryOut.model_validate(e) for e in entries]


# ---- Observability ----


@router.get("/observability/snapshot")
async def ops_snapshot(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, object]:
    return await eval_service.get_ops_snapshot(db)


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> PlainTextResponse:
    return PlainTextResponse(
        content=collector.prometheus_text(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
