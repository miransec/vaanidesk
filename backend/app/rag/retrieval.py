"""Keyword / vector / hybrid retrieval with in-SQL access control."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    ProcessingStatus,
    RetrievalStrategy,
    RetrievalTrace,
    User,
)
from app.rag.access import document_visible_to
from app.rag.embeddings import get_embedding_provider
from app.rag.injection import scan_evidence
from app.rag.rerank import RerankCandidate, get_reranker

# Reciprocal Rank Fusion constant (Cormack et al.)
RRF_K = 60


@dataclass
class Citation:
    document_title: str
    document_version: int
    section_label: str
    chunk_id: UUID
    source_type: str
    score: float


@dataclass
class RetrievalResult:
    strategy: RetrievalStrategy
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    confidence: float = 0.0
    no_answer: bool = False
    no_answer_reason: str | None = None
    lexical_scores: dict[str, float] = field(default_factory=dict)
    vector_scores: dict[str, float] = field(default_factory=dict)
    fused_scores: dict[str, float] = field(default_factory=dict)
    rerank_scores: dict[str, float] = field(default_factory=dict)
    candidate_ids: list[str] = field(default_factory=list)
    selected_ids: list[str] = field(default_factory=list)
    suspicious_evidence: bool = False
    latency_ms: int = 0
    trace_id: UUID | None = None


def _authorized_chunk_query(user: User) -> Select[Any]:
    return (
        select(KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentVersion)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .join(
            KnowledgeDocumentVersion,
            KnowledgeDocumentVersion.id == KnowledgeChunk.document_version_id,
        )
        .where(
            KnowledgeDocumentVersion.is_active.is_(True),
            KnowledgeDocumentVersion.processing_status == ProcessingStatus.READY,
            document_visible_to(user),
        )
    )


async def retrieve(
    *,
    db: AsyncSession,
    user: User,
    query: str,
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID,
    top_k: int = 5,
    candidate_k: int = 20,
    request_id: str,
    conversation_id: UUID | None = None,
    persist_trace: bool = True,
) -> RetrievalResult:
    started = time.perf_counter()
    settings = get_settings()
    threshold = float(getattr(settings, "rag_min_retrieval_confidence", 0.35))

    lexical: dict[str, float] = {}
    vector: dict[str, float] = {}
    fused: dict[str, float] = {}
    rerank_scores: dict[str, float] = {}
    chunk_map: dict[str, tuple[KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentVersion]] = {}

    if strategy in {
        RetrievalStrategy.KEYWORD,
        RetrievalStrategy.HYBRID,
        RetrievalStrategy.HYBRID_RERANK,
    }:
        lexical, lex_rows = await _keyword_search(db, user, query, candidate_k)
        for cid, row in lex_rows.items():
            chunk_map[cid] = row

    if strategy in {
        RetrievalStrategy.VECTOR,
        RetrievalStrategy.HYBRID,
        RetrievalStrategy.HYBRID_RERANK,
    }:
        vector, vec_rows = await _vector_search(db, user, query, candidate_k)
        for cid, row in vec_rows.items():
            chunk_map.setdefault(cid, row)

    if strategy == RetrievalStrategy.KEYWORD:
        ranked_ids = sorted(lexical, key=lexical.get, reverse=True)  # type: ignore[arg-type]
        fused = dict(lexical)
    elif strategy == RetrievalStrategy.VECTOR:
        ranked_ids = sorted(vector, key=vector.get, reverse=True)  # type: ignore[arg-type]
        fused = dict(vector)
    else:
        fused = _rrf_fuse(lexical, vector)
        ranked_ids = sorted(fused, key=fused.get, reverse=True)  # type: ignore[arg-type]

    candidate_ids = ranked_ids[:candidate_k]
    # Access already enforced in SQL — candidates are authorized only.
    selected_ids = candidate_ids[:top_k]

    if strategy == RetrievalStrategy.HYBRID_RERANK and candidate_ids:
        reranker = get_reranker()
        candidates = [
            RerankCandidate(
                chunk_id=UUID(cid),
                text=chunk_map[cid][0].text,
                base_score=fused.get(cid, 0.0),
            )
            for cid in candidate_ids
            if cid in chunk_map
        ]
        reranked = reranker.rerank(query, candidates)
        rerank_scores = {str(r.chunk_id): r.score for r in reranked}
        selected_ids = [str(r.chunk_id) for r in reranked[:top_k]]
        fused = {**fused, **{k: max(fused.get(k, 0.0), v) for k, v in rerank_scores.items()}}

    selected_rows = [chunk_map[cid] for cid in selected_ids if cid in chunk_map]
    confidence = _compute_confidence(
        strategy=strategy,
        selected_ids=selected_ids,
        lexical=lexical,
        vector=vector,
        fused=fused,
        rerank_scores=rerank_scores,
    )

    suspicious = False
    for chunk, _, _ in selected_rows:
        if scan_evidence(chunk.text).suspicious:
            suspicious = True
            break

    no_answer = False
    reason = None
    if not selected_rows:
        no_answer = True
        reason = "empty_results"
        confidence = 0.0
    elif confidence < threshold:
        no_answer = True
        reason = "below_confidence_threshold"
        selected_rows = []
        selected_ids = []

    citations: list[Citation] = []
    if not no_answer:
        for chunk, doc, ver in selected_rows:
            score = rerank_scores.get(str(chunk.id), fused.get(str(chunk.id), 0.0))
            citations.append(
                Citation(
                    document_title=doc.title,
                    document_version=ver.version_number,
                    section_label=chunk.section_label,
                    chunk_id=chunk.id,
                    source_type=doc.source_type.value,
                    score=float(score),
                )
            )

    result = RetrievalResult(
        strategy=strategy,
        chunks=[r[0] for r in selected_rows],
        citations=citations,
        confidence=confidence,
        no_answer=no_answer,
        no_answer_reason=reason,
        lexical_scores=lexical,
        vector_scores=vector,
        fused_scores=fused,
        rerank_scores=rerank_scores,
        candidate_ids=candidate_ids,
        selected_ids=selected_ids,
        suspicious_evidence=suspicious,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )

    if persist_trace:
        trace = RetrievalTrace(
            request_id=request_id,
            conversation_id=conversation_id,
            user_id=user.id,
            query=query[:2000],
            retrieval_strategy=strategy,
            candidate_chunk_ids=candidate_ids,
            selected_chunk_ids=selected_ids,
            lexical_scores={k: round(v, 6) for k, v in lexical.items()},
            vector_scores={k: round(v, 6) for k, v in vector.items()},
            fused_scores={k: round(v, 6) for k, v in fused.items()},
            rerank_scores={k: round(v, 6) for k, v in rerank_scores.items()},
            confidence=confidence,
            latency_ms=result.latency_ms,
            no_answer_reason=reason,
            citation_summary=[
                {
                    "title": c.document_title,
                    "version": c.document_version,
                    "section": c.section_label,
                    "chunk_id": str(c.chunk_id),
                    "score": c.score,
                }
                for c in citations
            ],
        )
        db.add(trace)
        await db.flush()
        result.trace_id = trace.id

    return result


ChunkRow = tuple[KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentVersion]


async def _keyword_search(
    db: AsyncSession, user: User, query: str, limit: int
) -> tuple[dict[str, float], dict[str, ChunkRow]]:
    ts_query = func.plainto_tsquery("simple", query)
    rank = func.ts_rank(KnowledgeChunk.search_vector, ts_query).label("rank")
    q = (
        _authorized_chunk_query(user)
        .add_columns(rank)
        .where(KnowledgeChunk.search_vector.op("@@")(ts_query))
        .order_by(text("rank DESC"))
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    scores: dict[str, float] = {}
    mapped: dict[str, ChunkRow] = {}
    for chunk, doc, ver, rank_val in rows:
        cid = str(chunk.id)
        scores[cid] = float(rank_val or 0.0)
        mapped[cid] = (chunk, doc, ver)
    return scores, mapped


async def _vector_search(
    db: AsyncSession, user: User, query: str, limit: int
) -> tuple[dict[str, float], dict[str, ChunkRow]]:
    emb = get_embedding_provider().embed(query)
    # cosine distance: smaller is better → convert to similarity
    distance = KnowledgeChunk.embedding.cosine_distance(emb)
    q = (
        _authorized_chunk_query(user)
        .add_columns(distance.label("dist"))
        .order_by(distance)
        .limit(limit)
    )
    rows = (await db.execute(q)).all()
    scores: dict[str, float] = {}
    mapped: dict[str, ChunkRow] = {}
    for chunk, doc, ver, dist in rows:
        cid = str(chunk.id)
        # pgvector cosine_distance is 1 - cos_sim for normalized vectors (0..2).
        scores[cid] = max(0.0, 1.0 - float(dist or 0.0))
        mapped[cid] = (chunk, doc, ver)
    return scores, mapped


def _rrf_fuse(
    lexical: dict[str, float], vector: dict[str, float], k: int = RRF_K
) -> dict[str, float]:
    """Reciprocal Rank Fusion: score(d) = Σ 1 / (k + rank_i(d))."""
    lex_ranked = sorted(lexical, key=lexical.get, reverse=True)  # type: ignore[arg-type]
    vec_ranked = sorted(vector, key=vector.get, reverse=True)  # type: ignore[arg-type]
    fused: dict[str, float] = {}
    for rank, cid in enumerate(lex_ranked, start=1):
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank)
    for rank, cid in enumerate(vec_ranked, start=1):
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (k + rank)
    return fused


def _compute_confidence(
    *,
    strategy: RetrievalStrategy,
    selected_ids: list[str],
    lexical: dict[str, float],
    vector: dict[str, float],
    fused: dict[str, float],
    rerank_scores: dict[str, float],
) -> float:
    """Blend absolute component scores so weak nearest-neighbors do not clear the gate."""
    if not selected_ids:
        return 0.0
    top = selected_ids[0]
    parts: list[float] = []
    if top in lexical:
        parts.append(max(0.0, min(1.0, float(lexical[top]) / 0.05)))
    if top in vector:
        parts.append(max(0.0, min(1.0, float(vector[top]))))
    if strategy in {RetrievalStrategy.HYBRID, RetrievalStrategy.HYBRID_RERANK}:
        max_rrf = 2.0 / (RRF_K + 1.0)
        parts.append(max(0.0, min(1.0, float(fused.get(top, 0.0)) / max_rrf)))
    if top in rerank_scores:
        parts.append(max(0.0, min(1.0, float(rerank_scores[top]))))
    if strategy == RetrievalStrategy.KEYWORD and top in lexical:
        return max(0.0, min(1.0, float(lexical[top]) / 0.05))
    if strategy == RetrievalStrategy.VECTOR and top in vector:
        return max(0.0, min(1.0, float(vector[top])))
    if not parts:
        return 0.0
    return max(0.0, min(1.0, sum(parts) / len(parts)))
