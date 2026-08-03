"""Phase 3 knowledge / RAG schema.

Revision ID: 0003_phase3
Revises: 0002_phase2
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase3"
down_revision: str | None = "0002_phase2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    source_type = postgresql.ENUM(
        "markdown", "text", "json", "policy", name="document_source_type", create_type=True
    )
    access_level = postgresql.ENUM(
        "public", "authenticated", "restricted", name="document_access_level", create_type=True
    )
    processing = postgresql.ENUM(
        "pending",
        "processing",
        "ready",
        "failed",
        "deactivated",
        name="processing_status",
        create_type=True,
    )
    ingest_status = postgresql.ENUM(
        "queued",
        "running",
        "succeeded",
        "failed",
        "skipped_duplicate",
        name="ingestion_job_status",
        create_type=True,
    )
    retrieval_strategy = postgresql.ENUM(
        "keyword",
        "vector",
        "hybrid",
        "hybrid_rerank",
        name="retrieval_strategy",
        create_type=True,
    )
    for e in (source_type, access_level, processing, ingest_status, retrieval_strategy):
        e.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "markdown", "text", "json", "policy", name="document_source_type", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "access_level",
            postgresql.ENUM(
                "public",
                "authenticated",
                "restricted",
                name="document_access_level",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("current_version", sa.Integer(), nullable=True),
        sa.Column("access_allowlist", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "knowledge_document_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("original_filename", sa.String(260), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("source_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "processing_status",
            postgresql.ENUM(
                "pending",
                "processing",
                "ready",
                "failed",
                "deactivated",
                name="processing_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "version_number", name="uq_knowledge_doc_version"),
    )
    op.create_index("ix_knowledge_versions_hash", "knowledge_document_versions", ["content_hash"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("section_label", sa.String(200), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("chunk_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["knowledge_document_versions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "document_version_id", "chunk_index", name="uq_knowledge_chunk_version_index"
        ),
    )
    op.create_index("ix_knowledge_chunks_document", "knowledge_chunks", ["document_id"])
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_search "
        "ON knowledge_chunks USING GIN (search_vector)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(
                "queued",
                "running",
                "succeeded",
                "failed",
                "skipped_duplicate",
                name="ingestion_job_status",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("stats", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["document_version_id"], ["knowledge_document_versions.id"], ondelete="SET NULL"
        ),
    )

    op.create_table(
        "retrieval_traces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("request_id", sa.String(64), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column(
            "retrieval_strategy",
            postgresql.ENUM(
                "keyword",
                "vector",
                "hybrid",
                "hybrid_rerank",
                name="retrieval_strategy",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("candidate_chunk_ids", postgresql.JSONB(), nullable=True),
        sa.Column("selected_chunk_ids", postgresql.JSONB(), nullable=True),
        sa.Column("lexical_scores", postgresql.JSONB(), nullable=True),
        sa.Column("vector_scores", postgresql.JSONB(), nullable=True),
        sa.Column("fused_scores", postgresql.JSONB(), nullable=True),
        sa.Column("rerank_scores", postgresql.JSONB(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("no_answer_reason", sa.String(200), nullable=True),
        sa.Column("citation_summary", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_retrieval_traces_request", "retrieval_traces", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_retrieval_traces_request", table_name="retrieval_traces")
    op.drop_table("retrieval_traces")
    op.drop_table("ingestion_jobs")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_embedding")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_chunks_search")
    op.drop_index("ix_knowledge_chunks_document", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_versions_hash", table_name="knowledge_document_versions")
    op.drop_table("knowledge_document_versions")
    op.drop_table("knowledge_documents")
    for name in (
        "retrieval_strategy",
        "ingestion_job_status",
        "processing_status",
        "document_access_level",
        "document_source_type",
    ):
        op.execute(f"DROP TYPE IF EXISTS {name}")
