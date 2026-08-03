"""Knowledge document service (routers stay thin)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models import (
    DocumentAccessLevel,
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievalStrategy,
    RetrievalTrace,
    User,
)
from app.rag.embeddings import get_embedding_provider
from app.rag.ingestion import (
    activate_version,
    deactivate_document,
    ingest_document,
    reindex_version,
)
from app.rag.retrieval import retrieve
from app.schemas.knowledge import (
    ActivateVersionRequest,
    CitationOut,
    IngestResultOut,
    KnowledgeDocumentCreate,
    KnowledgeDocumentDetail,
    KnowledgeDocumentOut,
    KnowledgeVersionOut,
    RetrievalChunkOut,
    RetrievalTestRequest,
    RetrievalTestResponse,
    RetrievalTraceOut,
)


async def create_document(
    *,
    db: AsyncSession,
    payload: KnowledgeDocumentCreate,
) -> IngestResultOut:
    result = await ingest_document(
        db=db,
        title=payload.title,
        raw=payload.content.encode("utf-8"),
        mime_type=payload.mime_type,
        filename=payload.filename or "upload.md",
        language=payload.language,
        access_level=DocumentAccessLevel(payload.access_level),
        access_allowlist=payload.access_allowlist,
        activate=payload.activate,
    )
    await db.commit()
    return IngestResultOut(
        document_id=UUID(result["document_id"]),
        version_id=UUID(result["version_id"]),
        version_number=int(result["version_number"]),
        status=str(result["status"]),
        job_id=UUID(result["job_id"]) if result.get("job_id") else None,
        chunk_count=result.get("chunk_count"),
        content_hash=result.get("content_hash"),
    )


async def list_documents(*, db: AsyncSession) -> list[KnowledgeDocumentOut]:
    rows = (
        (await db.execute(select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc())))
        .scalars()
        .all()
    )
    return [KnowledgeDocumentOut.model_validate(r) for r in rows]


async def get_document(*, db: AsyncSession, document_id: UUID) -> KnowledgeDocumentDetail:
    doc = (
        await db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .options(selectinload(KnowledgeDocument.versions))
        )
    ).scalar_one_or_none()
    if doc is None:
        raise AppError(code="document_not_found", message="Document not found.", status_code=404)
    versions_out: list[KnowledgeVersionOut] = []
    for ver in sorted(doc.versions, key=lambda v: v.version_number):
        count = (
            await db.execute(
                select(func.count())
                .select_from(KnowledgeChunk)
                .where(KnowledgeChunk.document_version_id == ver.id)
            )
        ).scalar_one()
        versions_out.append(
            KnowledgeVersionOut(
                id=ver.id,
                document_id=ver.document_id,
                version_number=ver.version_number,
                content_hash=ver.content_hash,
                original_filename=ver.original_filename,
                mime_type=ver.mime_type,
                processing_status=ver.processing_status.value,
                is_active=ver.is_active,
                created_at=ver.created_at,
                chunk_count=int(count),
            )
        )
    base = KnowledgeDocumentOut.model_validate(doc)
    return KnowledgeDocumentDetail(**base.model_dump(), versions=versions_out)


async def list_versions(*, db: AsyncSession, document_id: UUID) -> list[KnowledgeVersionOut]:
    detail = await get_document(db=db, document_id=document_id)
    return detail.versions


async def activate_document_version(
    *,
    db: AsyncSession,
    document_id: UUID,
    payload: ActivateVersionRequest,
) -> dict[str, object]:
    result = await activate_version(db=db, document_id=document_id, version_id=payload.version_id)
    await db.commit()
    return result


async def deactivate_doc(*, db: AsyncSession, document_id: UUID) -> dict[str, object]:
    result = await deactivate_document(db=db, document_id=document_id)
    await db.commit()
    return result


async def reindex_document_version(
    *,
    db: AsyncSession,
    document_id: UUID,
    version_id: UUID,
) -> dict[str, object]:
    result = await reindex_version(db=db, document_id=document_id, version_id=version_id)
    await db.commit()
    return result


async def run_retrieval_test(
    *,
    db: AsyncSession,
    user: User,
    payload: RetrievalTestRequest,
    request_id: str,
) -> RetrievalTestResponse:
    strategy = RetrievalStrategy(payload.strategy)
    result = await retrieve(
        db=db,
        user=user,
        query=payload.query,
        strategy=strategy,
        top_k=payload.top_k,
        request_id=request_id,
        conversation_id=None,
        persist_trace=payload.persist_trace,
    )
    await db.commit()
    chunks_out: list[RetrievalChunkOut] = []
    for chunk, cite in zip(result.chunks, result.citations, strict=False):
        chunks_out.append(
            RetrievalChunkOut(
                chunk_id=chunk.id,
                document_title=cite.document_title,
                document_version=cite.document_version,
                section_label=cite.section_label,
                text=chunk.text,
                score=cite.score,
            )
        )
    return RetrievalTestResponse(
        strategy=result.strategy.value,
        confidence=result.confidence,
        no_answer=result.no_answer,
        no_answer_reason=result.no_answer_reason,
        suspicious_evidence=result.suspicious_evidence,
        latency_ms=result.latency_ms,
        trace_id=result.trace_id,
        citations=[
            CitationOut(
                document_title=c.document_title,
                document_version=c.document_version,
                section_label=c.section_label,
                chunk_id=c.chunk_id,
                source_type=c.source_type,
                score=c.score,
            )
            for c in result.citations
        ],
        chunks=chunks_out,
        candidate_chunk_ids=result.candidate_ids,
        fused_scores={k: round(v, 6) for k, v in result.fused_scores.items()},
        embedding_disclaimer=get_embedding_provider().disclaimer,
    )


async def get_retrieval_trace(
    *,
    db: AsyncSession,
    user: User,
    trace_id: UUID,
) -> RetrievalTraceOut:
    trace = await db.get(RetrievalTrace, trace_id)
    if trace is None or trace.user_id != user.id:
        raise AppError(
            code="trace_not_found",
            message="Retrieval trace not found.",
            status_code=404,
        )
    return RetrievalTraceOut(
        id=trace.id,
        request_id=trace.request_id,
        conversation_id=trace.conversation_id,
        user_id=trace.user_id,
        query=trace.query,
        retrieval_strategy=trace.retrieval_strategy.value,
        candidate_chunk_ids=trace.candidate_chunk_ids,
        selected_chunk_ids=trace.selected_chunk_ids,
        lexical_scores=trace.lexical_scores,
        vector_scores=trace.vector_scores,
        fused_scores=trace.fused_scores,
        rerank_scores=trace.rerank_scores,
        confidence=trace.confidence,
        latency_ms=trace.latency_ms,
        no_answer_reason=trace.no_answer_reason,
        citation_summary=trace.citation_summary,
        created_at=trace.created_at,
    )
