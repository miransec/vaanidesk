"""Explicit Phase 2 support-agent workflow (not an autonomous loop)."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.intent import Intent, get_intent_classifier
from app.agents.language import get_language_detector
from app.agents.responses import respond
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import (
    AgentTrace,
    ToolExecution,
    ToolExecutionStatus,
    ToolRiskLevel,
    User,
    WorkflowStatus,
)
from app.security.confirmation import create_confirmation
from app.security.idempotency import begin_or_replay, complete_record, fail_record
from app.security.redaction import argument_hash, redact_mapping
from app.tools.registry import get_tool
from app.workflows.types import ConfirmationView, WorkflowResult

logger = logging.getLogger(__name__)


def _policy_retrieval_query(text: str) -> str:
    """Augment non-English policy asks with English lexical anchors for mock FTS/embeddings."""
    lower = text.lower()
    hints: list[str] = [text]
    pairs = [
        (("return", "वापसी", "परतावा", "wapas"), "return procedure unused items"),
        (("warranty", "वारंटी", "वॉरंटी"), "warranty terms coverage"),
        (("delivery", "डिलीवरी", "वितरण", "shipping"), "delivery policy shipping timeline"),
        (("cancel", "रद्द", "cancellation"), "cancellation policy order"),
        (("refund", "रिफंड"), "refund timeline policy"),
        (("damaged", "क्षतिग्रस्त", "टूटा"), "damaged products policy"),
        (("payment", "भुगतान", "dispute"), "payment disputes policy"),
        (("security", "सुरक्षा", "privacy"), "account security privacy"),
        (("escalat", "एस्केलेश", "मानव"), "customer support escalation"),
        (("नीति", "धोरण", "policy"), "policy"),
    ]
    for needles, hint in pairs:
        if any(n in lower or n in text for n in needles):
            hints.append(hint)
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for h in hints:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return " ".join(out)


async def _run_policy_retrieval(
    *,
    db: AsyncSession,
    user: User,
    conversation_id: UUID,
    message_id: UUID | None,
    text: str,
    request_id: str,
    language: Any,
    intent_result: Any,
    entities: dict[str, Any],
    started: float,
) -> WorkflowResult:
    from app.models import RetrievalStrategy
    from app.rag.injection import wrap_evidence
    from app.rag.retrieval import retrieve

    retrieval_query = _policy_retrieval_query(text)
    retrieval = await retrieve(
        db=db,
        user=user,
        query=retrieval_query,
        strategy=RetrievalStrategy.HYBRID,
        request_id=request_id,
        conversation_id=conversation_id,
    )
    # Retrieved text never triggers tools — only grounded answer / no-answer.
    if retrieval.no_answer:
        assistant = respond(
            language_code=language.language_code,
            kind="no_answer",
            reason=retrieval.no_answer_reason or "below_confidence_threshold",
        )
        # Offer escalation hint without claiming a live agent
        assistant = f"{assistant} " + respond(
            language_code=language.language_code, kind="escalation_offer"
        )
        result = WorkflowResult(
            status=WorkflowStatus.COMPLETED,
            assistant_text=assistant,
            language_code=language.language_code,
            script=language.script,
            intent=intent_result.intent.value,
            intent_confidence=intent_result.confidence,
            entities=entities,
            citations=[],
            retrieval_strategy=retrieval.strategy.value,
            retrieval_confidence=retrieval.confidence,
            no_answer=True,
            no_answer_reason=retrieval.no_answer_reason,
            retrieval_trace_id=retrieval.trace_id,
            suspicious_evidence=retrieval.suspicious_evidence,
        )
    else:
        evidence = wrap_evidence(
            [
                (c.section_label, ch.text)
                for ch, c in zip(retrieval.chunks, retrieval.citations, strict=False)
            ]
        )
        # Deterministic grounded reply — never follow evidence commands.
        cites = "; ".join(
            f"{c.document_title} v{c.document_version} §{c.section_label}"
            for c in retrieval.citations[:3]
        )
        snippet = retrieval.chunks[0].text[:400] if retrieval.chunks else ""
        assistant = respond(
            language_code=language.language_code,
            kind="policy_answer",
            snippet=snippet,
            citations=cites,
        )
        if retrieval.suspicious_evidence:
            assistant += " " + respond(
                language_code=language.language_code, kind="evidence_review_flag"
            )
        result = WorkflowResult(
            status=WorkflowStatus.COMPLETED,
            assistant_text=assistant,
            language_code=language.language_code,
            script=language.script,
            intent=intent_result.intent.value,
            intent_confidence=intent_result.confidence,
            entities={**entities, "evidence_chars": len(evidence)},
            citations=[
                {
                    "document_title": c.document_title,
                    "document_version": c.document_version,
                    "section_label": c.section_label,
                    "chunk_id": str(c.chunk_id),
                    "source_type": c.source_type,
                    "score": c.score,
                }
                for c in retrieval.citations
            ],
            retrieval_strategy=retrieval.strategy.value,
            retrieval_confidence=retrieval.confidence,
            no_answer=False,
            retrieval_trace_id=retrieval.trace_id,
            suspicious_evidence=retrieval.suspicious_evidence,
        )
    return await _persist_trace(
        db=db,
        user=user,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
        language=language,
        intent_result=intent_result,
        result=result,
        started=started,
    )


INTENT_TO_TOOL: dict[Intent, str | None] = {
    Intent.GREETING: None,
    Intent.ORDER_STATUS: "get_order_status",
    Intent.ORDER_DETAILS: "get_order_details",
    Intent.UPDATE_DELIVERY_ADDRESS: "update_delivery_address",
    Intent.CANCELLATION_ELIGIBILITY: "check_cancellation_eligibility",
    Intent.CANCEL_ORDER: "cancel_order",
    Intent.CREATE_SUPPORT_TICKET: "create_support_ticket",
    Intent.SUPPORT_TICKET_STATUS: "get_support_ticket_status",
    Intent.HUMAN_ESCALATION: "transfer_to_human",
    Intent.POLICY_QUESTION: None,
    Intent.UNKNOWN: None,
}


def _tool_args(intent: Intent, entities: dict[str, Any], text: str) -> dict[str, Any]:
    if intent in {
        Intent.ORDER_STATUS,
        Intent.ORDER_DETAILS,
        Intent.CANCELLATION_ELIGIBILITY,
        Intent.CANCEL_ORDER,
    }:
        return {"order_ref": entities["order_ref"]} if "order_ref" in entities else {}
    if intent == Intent.UPDATE_DELIVERY_ADDRESS:
        args: dict[str, Any] = {}
        if "order_ref" in entities:
            args["order_ref"] = entities["order_ref"]
        if "new_address" in entities:
            args["new_address"] = entities["new_address"]
        return args
    if intent == Intent.SUPPORT_TICKET_STATUS:
        return {"ticket_ref": entities["ticket_ref"]} if "ticket_ref" in entities else {}
    if intent == Intent.CREATE_SUPPORT_TICKET:
        desc = entities.get("issue_description") or text.strip()
        title = desc[:80]
        return {"title": title or "Support request", "description": desc}
    if intent == Intent.HUMAN_ESCALATION:
        return {"reason": text.strip()[:1000] or "User requested human support"}
    return {}


async def run_support_workflow(
    *,
    db: AsyncSession,
    user: User,
    conversation_id: UUID,
    message_id: UUID | None,
    text: str,
    request_id: str,
    idempotency_key: str | None = None,
) -> WorkflowResult:
    started = time.perf_counter()
    settings = get_settings()
    threshold = float(getattr(settings, "agent_confidence_escalate_threshold", 0.45))

    language = get_language_detector().detect(text)
    intent_result = get_intent_classifier().classify(text, language)
    intent = intent_result.intent
    entities = dict(intent_result.entities)

    # Greeting short-circuit
    if intent == Intent.GREETING:
        result = WorkflowResult(
            status=WorkflowStatus.COMPLETED,
            assistant_text=respond(language_code=language.language_code, kind="greeting"),
            language_code=language.language_code,
            script=language.script,
            intent=intent.value,
            intent_confidence=intent_result.confidence,
            entities=entities,
        )
        return await _persist_trace(
            db=db,
            user=user,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            language=language,
            intent_result=intent_result,
            result=result,
            started=started,
        )

    # Clarification
    if intent_result.missing_fields:
        question = intent_result.clarification_question or "Please provide more details."
        result = WorkflowResult(
            status=WorkflowStatus.CLARIFICATION_REQUIRED,
            assistant_text=respond(
                language_code=language.language_code, kind="clarification", question=question
            ),
            language_code=language.language_code,
            script=language.script,
            intent=intent.value,
            intent_confidence=intent_result.confidence,
            clarification_required=True,
            entities=entities,
        )
        return await _persist_trace(
            db=db,
            user=user,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            language=language,
            intent_result=intent_result,
            result=result,
            started=started,
        )

    # Policy / knowledge retrieval (separate from tools)
    if intent == Intent.POLICY_QUESTION:
        return await _run_policy_retrieval(
            db=db,
            user=user,
            conversation_id=conversation_id,
            message_id=message_id,
            text=text,
            request_id=request_id,
            language=language,
            intent_result=intent_result,
            entities=entities,
            started=started,
        )

    # Low confidence / unknown → escalate via transfer_to_human
    if intent == Intent.UNKNOWN or intent_result.confidence < threshold:
        tool = get_tool("transfer_to_human")
        reason = (
            intent_result.clarification_question
            or f"Low confidence ({intent_result.confidence:.2f}) or unknown intent"
        )
        tool_result = await tool.execute(
            db=db,
            user=user,
            arguments={"reason": reason[:1000]},
            conversation_id=conversation_id,
        )
        result = WorkflowResult(
            status=WorkflowStatus.ESCALATED,
            assistant_text=respond(
                language_code=language.language_code,
                kind="unknown_escalation",
                ticket_ref=tool_result["ticket_ref"],
            ),
            language_code=language.language_code,
            script=language.script,
            intent=intent.value,
            intent_confidence=intent_result.confidence,
            selected_tool="transfer_to_human",
            tool_execution_status=ToolExecutionStatus.SUCCESS.value,
            escalation_required=True,
            escalation_reason=reason,
            tool_result=tool_result,
            entities=entities,
        )
        return await _persist_trace(
            db=db,
            user=user,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            language=language,
            intent_result=intent_result,
            result=result,
            started=started,
            tool_name="transfer_to_human",
            tool_args={"reason": reason[:200]},
            tool_status=ToolExecutionStatus.SUCCESS,
            risk=ToolRiskLevel.MODERATE,
            idempotency_key=idempotency_key,
        )

    tool_name = INTENT_TO_TOOL.get(intent)
    if tool_name is None:
        result = WorkflowResult(
            status=WorkflowStatus.FAILED,
            assistant_text=respond(
                language_code=language.language_code, kind="error", code="no_tool"
            ),
            language_code=language.language_code,
            script=language.script,
            intent=intent.value,
            intent_confidence=intent_result.confidence,
            entities=entities,
        )
        return await _persist_trace(
            db=db,
            user=user,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            language=language,
            intent_result=intent_result,
            result=result,
            started=started,
        )

    tool = get_tool(tool_name)
    args = _tool_args(intent, entities, text)

    # Validate args early
    try:
        tool.input_model.model_validate(args)
    except Exception as exc:  # noqa: BLE001
        result = WorkflowResult(
            status=WorkflowStatus.CLARIFICATION_REQUIRED,
            assistant_text=respond(
                language_code=language.language_code,
                kind="clarification",
                question=intent_result.clarification_question or str(exc),
            ),
            language_code=language.language_code,
            script=language.script,
            intent=intent.value,
            intent_confidence=intent_result.confidence,
            selected_tool=tool_name,
            clarification_required=True,
            entities=entities,
        )
        return await _persist_trace(
            db=db,
            user=user,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            language=language,
            intent_result=intent_result,
            result=result,
            started=started,
            tool_name=tool_name,
            tool_args=args,
            tool_status=ToolExecutionStatus.REJECTED,
            risk=tool.risk_level,
        )

    # Confirmation gate for high-risk tools
    if tool.requires_confirmation:
        summary = _confirmation_summary(tool_name, args)
        try:
            confirmation = await create_confirmation(
                user_id=user.id,
                tool_name=tool_name,
                arguments=args,
                conversation_id=conversation_id,
                request_id=request_id,
                summary=summary,
                language_code=language.language_code,
                idempotency_key=idempotency_key,
            )
        except AppError:
            # Fail closed (e.g. Redis unavailable → HTTP 503). No sensitive mutation.
            raise

        kind = "confirm_cancel" if tool_name == "cancel_order" else "confirm_address"
        assistant = respond(
            language_code=language.language_code,
            kind=kind,
            order_ref=args.get("order_ref", ""),
            address=args.get("new_address", ""),
        )
        result = WorkflowResult(
            status=WorkflowStatus.CONFIRMATION_REQUIRED,
            assistant_text=assistant,
            language_code=language.language_code,
            script=language.script,
            intent=intent.value,
            intent_confidence=intent_result.confidence,
            selected_tool=tool_name,
            tool_execution_status=ToolExecutionStatus.CONFIRMATION_REQUIRED.value,
            confirmation_required=True,
            confirmation=ConfirmationView(
                token=confirmation.token,
                action=tool_name,
                summary=summary,
                expires_at=confirmation.expires_at.isoformat(),
            ),
            entities=entities,
        )
        return await _persist_trace(
            db=db,
            user=user,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            language=language,
            intent_result=intent_result,
            result=result,
            started=started,
            tool_name=tool_name,
            tool_args=args,
            tool_status=ToolExecutionStatus.CONFIRMATION_REQUIRED,
            risk=tool.risk_level,
            idempotency_key=idempotency_key,
        )

    # Execute (with optional idempotency)
    return await execute_tool_and_respond(
        db=db,
        user=user,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
        language_code=language.language_code,
        script=language.script,
        intent_result=intent_result,
        entities=entities,
        tool_name=tool_name,
        args=args,
        idempotency_key=idempotency_key,
        started=started,
        language=language,
    )


async def execute_tool_and_respond(
    *,
    db: AsyncSession,
    user: User,
    conversation_id: UUID,
    message_id: UUID | None,
    request_id: str,
    language_code: str,
    script: str,
    intent_result: Any,
    entities: dict[str, Any],
    tool_name: str,
    args: dict[str, Any],
    idempotency_key: str | None,
    started: float,
    language: Any,
) -> WorkflowResult:
    tool = get_tool(tool_name)
    record = None
    replay = None
    effective_key = idempotency_key
    if tool.supports_idempotency:
        if not effective_key:
            # Derive stable key from user+tool+args for moderate tools without client key.
            effective_key = f"auto:{tool_name}:{argument_hash(args)}"
        record, replay = await begin_or_replay(
            db=db,
            user_id=user.id,
            tool_name=tool_name,
            arguments=args,
            idempotency_key=effective_key,
        )
        if replay is not None:
            result = _result_from_tool(
                tool_name=tool_name,
                tool_result=replay,
                language_code=language_code,
                script=script,
                intent_result=intent_result,
                entities=entities,
                status=WorkflowStatus.COMPLETED,
                tool_status=ToolExecutionStatus.SUCCESS.value,
            )
            return await _persist_trace(
                db=db,
                user=user,
                conversation_id=conversation_id,
                message_id=message_id,
                request_id=request_id,
                language=language,
                intent_result=intent_result,
                result=result,
                started=started,
                tool_name=tool_name,
                tool_args=args,
                tool_status=ToolExecutionStatus.SUCCESS,
                risk=tool.risk_level,
                idempotency_key=effective_key,
            )

    try:
        tool_started = time.perf_counter()
        tool_result = await tool.execute(
            db=db,
            user=user,
            arguments=args,
            conversation_id=conversation_id,
        )
        duration_ms = int((time.perf_counter() - tool_started) * 1000)
        if record is not None:
            await complete_record(record=record, result=tool_result)
        result = _result_from_tool(
            tool_name=tool_name,
            tool_result=tool_result,
            language_code=language_code,
            script=script,
            intent_result=intent_result,
            entities=entities,
            status=WorkflowStatus.COMPLETED
            if tool_name != "transfer_to_human"
            else WorkflowStatus.ESCALATED,
            tool_status=ToolExecutionStatus.SUCCESS.value,
        )
        if tool_name == "transfer_to_human":
            result.escalation_required = True
            result.escalation_reason = args.get("reason")
        return await _persist_trace(
            db=db,
            user=user,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            language=language,
            intent_result=intent_result,
            result=result,
            started=started,
            tool_name=tool_name,
            tool_args=args,
            tool_status=ToolExecutionStatus.SUCCESS,
            risk=tool.risk_level,
            idempotency_key=effective_key,
            duration_ms=duration_ms,
        )
    except AppError as exc:
        if record is not None:
            await fail_record(record=record, error={"code": exc.code, "message": exc.message})
        if exc.code in {"order_not_found", "ticket_not_found"}:
            assistant = respond(
                language_code=language_code,
                kind="not_found",
                ref=args.get("order_ref") or args.get("ticket_ref") or "that item",
            )
        else:
            assistant = respond(language_code=language_code, kind="error", code=exc.code)
        result = WorkflowResult(
            status=WorkflowStatus.FAILED,
            assistant_text=assistant,
            language_code=language_code,
            script=script,
            intent=intent_result.intent.value,
            intent_confidence=intent_result.confidence,
            selected_tool=tool_name,
            tool_execution_status=ToolExecutionStatus.FAILED.value,
            entities=entities,
        )
        return await _persist_trace(
            db=db,
            user=user,
            conversation_id=conversation_id,
            message_id=message_id,
            request_id=request_id,
            language=language,
            intent_result=intent_result,
            result=result,
            started=started,
            tool_name=tool_name,
            tool_args=args,
            tool_status=ToolExecutionStatus.FAILED,
            risk=tool.risk_level,
            idempotency_key=effective_key,
            error_code=exc.code,
        )


def _confirmation_summary(tool_name: str, args: dict[str, Any]) -> str:
    if tool_name == "cancel_order":
        return f"Cancel order {args.get('order_ref')}"
    if tool_name == "update_delivery_address":
        return f"Change delivery address for {args.get('order_ref')}"
    return f"Confirm {tool_name}"


def _result_from_tool(
    *,
    tool_name: str,
    tool_result: dict[str, Any],
    language_code: str,
    script: str,
    intent_result: Any,
    entities: dict[str, Any],
    status: WorkflowStatus,
    tool_status: str,
) -> WorkflowResult:
    if tool_name == "get_order_status":
        text = respond(
            language_code=language_code,
            kind="order_status",
            order_ref=tool_result["order_ref"],
            status=tool_result["status"],
            address=tool_result.get("delivery_address") or "—",
        )
    elif tool_name == "get_order_details":
        items = ", ".join(
            f"{i.get('name')}×{i.get('quantity')}" for i in tool_result.get("items", [])
        )
        text = respond(
            language_code=language_code,
            kind="order_details",
            order_ref=tool_result["order_ref"],
            status=tool_result["status"],
            currency=tool_result.get("currency", "INR"),
            total=tool_result.get("total_amount"),
            items=items or "—",
            address=tool_result.get("delivery_address") or "—",
        )
    elif tool_name == "check_cancellation_eligibility":
        kind = "cancel_eligibility_yes" if tool_result.get("eligible") else "cancel_eligibility_no"
        text = respond(
            language_code=language_code,
            kind=kind,
            order_ref=tool_result["order_ref"],
            reason=tool_result.get("reason", ""),
        )
    elif tool_name == "cancel_order":
        text = respond(
            language_code=language_code,
            kind="cancelled",
            order_ref=tool_result["order_ref"],
        )
    elif tool_name == "update_delivery_address":
        text = respond(
            language_code=language_code,
            kind="address_updated",
            order_ref=tool_result["order_ref"],
            address=tool_result.get("delivery_address", ""),
        )
    elif tool_name == "create_support_ticket":
        text = respond(
            language_code=language_code,
            kind="ticket_created",
            ticket_ref=tool_result["ticket_ref"],
            status=tool_result["status"],
        )
    elif tool_name == "get_support_ticket_status":
        text = respond(
            language_code=language_code,
            kind="ticket_status",
            ticket_ref=tool_result["ticket_ref"],
            status=tool_result["status"],
            priority=tool_result["priority"],
        )
    elif tool_name == "transfer_to_human":
        text = respond(
            language_code=language_code,
            kind="escalated",
            ticket_ref=tool_result["ticket_ref"],
        )
    else:
        text = str(tool_result)

    return WorkflowResult(
        status=status,
        assistant_text=text,
        language_code=language_code,
        script=script,
        intent=intent_result.intent.value,
        intent_confidence=intent_result.confidence,
        selected_tool=tool_name,
        tool_execution_status=tool_status,
        tool_result=tool_result,
        entities=entities,
        escalation_required=tool_name == "transfer_to_human",
    )


async def _persist_trace(
    *,
    db: AsyncSession,
    user: User,
    conversation_id: UUID,
    message_id: UUID | None,
    request_id: str,
    language: Any,
    intent_result: Any,
    result: WorkflowResult,
    started: float,
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    tool_status: ToolExecutionStatus | None = None,
    risk: ToolRiskLevel | None = None,
    idempotency_key: str | None = None,
    error_code: str | None = None,
    duration_ms: int | None = None,
) -> WorkflowResult:
    latency = int((time.perf_counter() - started) * 1000)
    result.latency_ms = latency
    trace = AgentTrace(
        id=uuid4(),
        request_id=request_id,
        user_id=user.id,
        conversation_id=conversation_id,
        message_id=message_id,
        detected_language=result.language_code,
        detected_script=result.script,
        intent=result.intent,
        intent_confidence=result.intent_confidence,
        extracted_entities=redact_mapping(result.entities),
        selected_tool=result.selected_tool,
        risk_level=risk.value if risk else None,
        clarification_required=result.clarification_required,
        confirmation_required=result.confirmation_required,
        escalation_required=result.escalation_required,
        escalation_reason=result.escalation_reason,
        workflow_status=result.status,
        provider_name=result.provider_name,
        total_latency_ms=latency,
    )
    db.add(trace)
    await db.flush()
    result.trace_id = trace.id

    if tool_name and tool_status and risk:
        db.add(
            ToolExecution(
                id=uuid4(),
                request_id=request_id,
                trace_id=trace.id,
                conversation_id=conversation_id,
                user_id=user.id,
                tool_name=tool_name,
                risk_level=risk,
                argument_summary=redact_mapping(tool_args),
                argument_hash=argument_hash(tool_args or {}),
                execution_status=tool_status,
                error_code=error_code,
                duration_ms=duration_ms,
                idempotency_key=idempotency_key,
            )
        )
        await db.flush()
    return result
