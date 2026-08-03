"""Phase 3 knowledge / RAG models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

EMBEDDING_DIM = 384


class DocumentSourceType(StrEnum):
    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"
    POLICY = "policy"


class DocumentAccessLevel(StrEnum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    RESTRICTED = "restricted"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DEACTIVATED = "deactivated"


class IngestionJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED_DUPLICATE = "skipped_duplicate"


class RetrievalStrategy(StrEnum):
    KEYWORD = "keyword"
    VECTOR = "vector"
    HYBRID = "hybrid"
    HYBRID_RERANK = "hybrid_rerank"


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[DocumentSourceType] = mapped_column(
        Enum(
            DocumentSourceType,
            name="document_source_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    access_level: Mapped[DocumentAccessLevel] = mapped_column(
        Enum(
            DocumentAccessLevel,
            name="document_access_level",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=DocumentAccessLevel.AUTHENTICATED,
    )
    current_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Optional allow-list of demo_keys for RESTRICTED docs (JSON list).
    access_allowlist: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    versions: Mapped[list[KnowledgeDocumentVersion]] = relationship(back_populates="document")
    chunks: Mapped[list[KnowledgeChunk]] = relationship(back_populates="document")


class KnowledgeDocumentVersion(Base):
    __tablename__ = "knowledge_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_knowledge_doc_version"),
        Index("ix_knowledge_versions_hash", "content_hash"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(260), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(
            ProcessingStatus,
            name="processing_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ProcessingStatus.PENDING,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[KnowledgeDocument] = relationship(back_populates="versions")
    chunks: Mapped[list[KnowledgeChunk]] = relationship(back_populates="document_version")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id", "chunk_index", name="uq_knowledge_chunk_version_index"
        ),
        Index("ix_knowledge_chunks_document", "document_id"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_label: Mapped[str] = mapped_column(String(200), nullable=False, default="body")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en")
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    search_vector = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")
    document_version: Mapped[KnowledgeDocumentVersion] = relationship(back_populates="chunks")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_version_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_document_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[IngestionJobStatus] = mapped_column(
        Enum(
            IngestionJobStatus,
            name="ingestion_job_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=IngestionJobStatus.QUEUED,
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RetrievalTrace(Base):
    __tablename__ = "retrieval_traces"
    __table_args__ = (Index("ix_retrieval_traces_request", "request_id"),)

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_strategy: Mapped[RetrievalStrategy] = mapped_column(
        Enum(
            RetrievalStrategy,
            name="retrieval_strategy",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    candidate_chunk_ids: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    selected_chunk_ids: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    lexical_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    vector_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    fused_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    rerank_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    no_answer_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Never store full unauthorized chunk text; optional safe titles only.
    citation_summary: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
