"""Typed request/response schemas for Phase 3 knowledge APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeDocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=500_000)
    mime_type: Literal["text/markdown", "text/plain", "application/json"] = "text/markdown"
    filename: str | None = None
    language: str | None = None
    access_level: Literal["public", "authenticated", "restricted"] = "authenticated"
    access_allowlist: list[str] | None = None
    activate: bool = True


class KnowledgeDocumentOut(BaseModel):
    id: UUID
    title: str
    source_type: str
    language: str
    is_active: bool
    access_level: str
    current_version: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeVersionOut(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    content_hash: str
    original_filename: str | None
    mime_type: str
    processing_status: str
    is_active: bool
    created_at: datetime
    chunk_count: int = 0

    model_config = {"from_attributes": True}


class KnowledgeDocumentDetail(KnowledgeDocumentOut):
    versions: list[KnowledgeVersionOut] = Field(default_factory=list)


class IngestResultOut(BaseModel):
    document_id: UUID
    version_id: UUID
    version_number: int
    status: str
    job_id: UUID | None = None
    chunk_count: int | None = None
    content_hash: str | None = None


class CitationOut(BaseModel):
    document_title: str
    document_version: int
    section_label: str
    chunk_id: UUID
    source_type: str
    score: float


class RetrievalTestRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    strategy: Literal["keyword", "vector", "hybrid", "hybrid_rerank"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=20)
    persist_trace: bool = True


class RetrievalChunkOut(BaseModel):
    chunk_id: UUID
    document_title: str
    document_version: int
    section_label: str
    text: str
    score: float


class RetrievalTestResponse(BaseModel):
    strategy: str
    confidence: float
    no_answer: bool
    no_answer_reason: str | None = None
    suspicious_evidence: bool = False
    latency_ms: int
    trace_id: UUID | None = None
    citations: list[CitationOut] = Field(default_factory=list)
    chunks: list[RetrievalChunkOut] = Field(default_factory=list)
    candidate_chunk_ids: list[str] = Field(default_factory=list)
    fused_scores: dict[str, float] = Field(default_factory=dict)
    embedding_disclaimer: str = (
        "Deterministic lexical embedding baseline for local development and testing "
        "— not production semantic embeddings."
    )


class RetrievalTraceOut(BaseModel):
    id: UUID
    request_id: str
    conversation_id: UUID | None
    user_id: UUID
    query: str
    retrieval_strategy: str
    candidate_chunk_ids: list[Any] | None = None
    selected_chunk_ids: list[Any] | None = None
    lexical_scores: dict[str, Any] | None = None
    vector_scores: dict[str, Any] | None = None
    fused_scores: dict[str, Any] | None = None
    rerank_scores: dict[str, Any] | None = None
    confidence: float | None = None
    latency_ms: int | None = None
    no_answer_reason: str | None = None
    citation_summary: list[Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivateVersionRequest(BaseModel):
    version_id: UUID
