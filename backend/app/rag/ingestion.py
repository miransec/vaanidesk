"""Document ingestion pipeline (Phase 3)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.language import get_language_detector
from app.core.errors import AppError
from app.models import (
    DocumentAccessLevel,
    DocumentSourceType,
    IngestionJob,
    IngestionJobStatus,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    ProcessingStatus,
)
from app.rag.chunking import chunk_document
from app.rag.embeddings import get_embedding_provider

ALLOWED_MIME = {
    "text/markdown": DocumentSourceType.MARKDOWN,
    "text/plain": DocumentSourceType.TEXT,
    "application/json": DocumentSourceType.JSON,
}
MAX_BYTES = 512_000


def content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def normalize_payload(
    *,
    raw: bytes,
    mime_type: str,
    filename: str | None,
) -> tuple[str, DocumentSourceType, dict[str, Any]]:
    if len(raw) > MAX_BYTES:
        raise AppError(
            code="document_too_large",
            message=f"Document exceeds {MAX_BYTES} bytes.",
            status_code=413,
        )
    mime = mime_type.split(";")[0].strip().lower()
    if mime not in ALLOWED_MIME:
        raise AppError(
            code="unsupported_mime_type",
            message=f"Unsupported MIME type: {mime}",
            status_code=415,
        )
    source_type = ALLOWED_MIME[mime]
    try:
        text_body = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError(
            code="invalid_encoding",
            message="Document must be UTF-8 text.",
            status_code=400,
        ) from exc

    meta: dict[str, Any] = {"filename": filename, "mime_type": mime}
    if source_type == DocumentSourceType.JSON:
        try:
            data = json.loads(text_body)
        except json.JSONDecodeError as exc:
            raise AppError(
                code="invalid_json", message="Invalid JSON document.", status_code=400
            ) from exc
        if not isinstance(data, dict):
            raise AppError(
                code="invalid_json_shape",
                message="JSON document must be an object with text fields.",
                status_code=400,
            )
        parts = []
        for key in ("title", "summary", "body", "content", "policy"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
        if not parts:
            raise AppError(
                code="json_missing_text",
                message="JSON must include approved text fields (body/content/policy).",
                status_code=400,
            )
        text_body = "\n\n".join(parts)
        meta["json_keys"] = [k for k in data if isinstance(data.get(k), str)]
    return text_body.strip(), source_type, meta


async def ingest_document(
    *,
    db: AsyncSession,
    title: str,
    raw: bytes,
    mime_type: str,
    filename: str | None = None,
    language: str | None = None,
    access_level: DocumentAccessLevel = DocumentAccessLevel.AUTHENTICATED,
    access_allowlist: list[str] | None = None,
    document_id: UUID | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    body, source_type, meta = normalize_payload(raw=raw, mime_type=mime_type, filename=filename)
    # Never execute document contents — treat as inert text only.
    digest = content_hash(body)
    job = IngestionJob(
        id=uuid4(),
        status=IngestionJobStatus.RUNNING,
        content_hash=digest,
    )
    db.add(job)
    await db.flush()

    try:
        if document_id is None:
            # Spec: avoid duplicate versions when content hash matches for this document.
            doc = KnowledgeDocument(
                id=uuid4(),
                title=title.strip()[:300],
                source_type=source_type,
                language=language or get_language_detector().detect(body[:500]).language_code,
                is_active=True,
                access_level=access_level,
                access_allowlist=access_allowlist,
            )
            db.add(doc)
            await db.flush()
            version_number = 1
        else:
            found = await db.get(KnowledgeDocument, document_id)
            if found is None:
                raise AppError(
                    code="document_not_found", message="Document not found.", status_code=404
                )
            doc = found
            # Same hash on this document → duplicate
            existing = (
                await db.execute(
                    select(KnowledgeDocumentVersion).where(
                        KnowledgeDocumentVersion.document_id == doc.id,
                        KnowledgeDocumentVersion.content_hash == digest,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                job.status = IngestionJobStatus.SKIPPED_DUPLICATE
                job.document_id = doc.id
                job.document_version_id = existing.id
                job.completed_at = datetime.now(UTC)
                job.stats = {"duplicate_of_version": existing.version_number}
                await db.flush()
                return {
                    "document_id": str(doc.id),
                    "version_id": str(existing.id),
                    "version_number": existing.version_number,
                    "status": "skipped_duplicate",
                    "job_id": str(job.id),
                }
            max_v = (
                await db.execute(
                    select(KnowledgeDocumentVersion.version_number)
                    .where(KnowledgeDocumentVersion.document_id == doc.id)
                    .order_by(KnowledgeDocumentVersion.version_number.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            version_number = int(max_v or 0) + 1

        version = KnowledgeDocumentVersion(
            id=uuid4(),
            document_id=doc.id,
            version_number=version_number,
            content_hash=digest,
            original_filename=filename,
            mime_type=mime_type.split(";")[0].strip().lower(),
            source_metadata=meta,
            processing_status=ProcessingStatus.PROCESSING,
            is_active=False,
            body_text=body,
        )
        db.add(version)
        await db.flush()

        chunks = chunk_document(body)
        embedder = get_embedding_provider()
        for ch in chunks:
            emb = embedder.embed(ch.text)
            chunk = KnowledgeChunk(
                id=uuid4(),
                document_id=doc.id,
                document_version_id=version.id,
                chunk_index=ch.index,
                section_label=ch.section_label,
                text=ch.text,
                char_count=len(ch.text),
                language=doc.language,
                chunk_metadata={"embedding_provider": embedder.name},
                embedding=emb,
            )
            db.add(chunk)
            await db.flush()
            await db.execute(
                text(
                    "UPDATE knowledge_chunks SET search_vector = "
                    "to_tsvector('simple', :body) WHERE id = :id"
                ),
                {"body": ch.text, "id": chunk.id},
            )

        if activate:
            await db.execute(
                update(KnowledgeDocumentVersion)
                .where(KnowledgeDocumentVersion.document_id == doc.id)
                .values(is_active=False, processing_status=ProcessingStatus.DEACTIVATED)
            )
            version.is_active = True
            version.processing_status = ProcessingStatus.READY
            doc.current_version = version_number
            doc.updated_at = datetime.now(UTC)
        else:
            version.processing_status = ProcessingStatus.READY

        job.status = IngestionJobStatus.SUCCEEDED
        job.document_id = doc.id
        job.document_version_id = version.id
        job.completed_at = datetime.now(UTC)
        job.stats = {
            "chunk_count": len(chunks),
            "version_number": version_number,
            "embedding_provider": embedder.name,
            "embedding_disclaimer": embedder.disclaimer,
        }
        await db.flush()
        return {
            "document_id": str(doc.id),
            "version_id": str(version.id),
            "version_number": version_number,
            "status": "succeeded",
            "chunk_count": len(chunks),
            "job_id": str(job.id),
            "content_hash": digest,
        }
    except AppError as exc:
        job.status = IngestionJobStatus.FAILED
        job.error_message = exc.message
        job.completed_at = datetime.now(UTC)
        await db.flush()
        raise
    except Exception as exc:  # noqa: BLE001
        job.status = IngestionJobStatus.FAILED
        job.error_message = type(exc).__name__
        job.completed_at = datetime.now(UTC)
        await db.flush()
        raise AppError(
            code="ingestion_failed",
            message="Ingestion failed.",
            status_code=500,
            details={"error_type": type(exc).__name__},
        ) from exc


async def activate_version(
    *,
    db: AsyncSession,
    document_id: UUID,
    version_id: UUID,
) -> dict[str, Any]:
    doc = await db.get(KnowledgeDocument, document_id)
    if doc is None:
        raise AppError(code="document_not_found", message="Document not found.", status_code=404)
    version = await db.get(KnowledgeDocumentVersion, version_id)
    if version is None or version.document_id != document_id:
        raise AppError(code="version_not_found", message="Version not found.", status_code=404)
    await db.execute(
        update(KnowledgeDocumentVersion)
        .where(KnowledgeDocumentVersion.document_id == document_id)
        .values(is_active=False, processing_status=ProcessingStatus.DEACTIVATED)
    )
    version.is_active = True
    version.processing_status = ProcessingStatus.READY
    doc.current_version = version.version_number
    doc.is_active = True
    doc.updated_at = datetime.now(UTC)
    await db.flush()
    return {
        "document_id": str(document_id),
        "version_id": str(version_id),
        "version_number": version.version_number,
        "status": "activated",
    }


async def deactivate_document(*, db: AsyncSession, document_id: UUID) -> dict[str, Any]:
    doc = await db.get(KnowledgeDocument, document_id)
    if doc is None:
        raise AppError(code="document_not_found", message="Document not found.", status_code=404)
    doc.is_active = False
    await db.execute(
        update(KnowledgeDocumentVersion)
        .where(KnowledgeDocumentVersion.document_id == document_id)
        .values(is_active=False, processing_status=ProcessingStatus.DEACTIVATED)
    )
    doc.updated_at = datetime.now(UTC)
    await db.flush()
    return {"document_id": str(document_id), "status": "deactivated"}


async def reindex_version(
    *, db: AsyncSession, document_id: UUID, version_id: UUID
) -> dict[str, Any]:
    """Rebuild chunks + embeddings + tsvectors for an existing version body."""
    from sqlalchemy import delete

    doc = await db.get(KnowledgeDocument, document_id)
    if doc is None:
        raise AppError(code="document_not_found", message="Document not found.", status_code=404)
    version = await db.get(KnowledgeDocumentVersion, version_id)
    if version is None or version.document_id != document_id:
        raise AppError(code="version_not_found", message="Version not found.", status_code=404)

    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_version_id == version_id))
    version.processing_status = ProcessingStatus.PROCESSING
    await db.flush()

    chunks = chunk_document(version.body_text)
    embedder = get_embedding_provider()
    for ch in chunks:
        emb = embedder.embed(ch.text)
        chunk = KnowledgeChunk(
            id=uuid4(),
            document_id=doc.id,
            document_version_id=version.id,
            chunk_index=ch.index,
            section_label=ch.section_label,
            text=ch.text,
            char_count=len(ch.text),
            language=doc.language,
            chunk_metadata={"embedding_provider": embedder.name, "reindexed": True},
            embedding=emb,
        )
        db.add(chunk)
        await db.flush()
        await db.execute(
            text(
                "UPDATE knowledge_chunks SET search_vector = "
                "to_tsvector('simple', :body) WHERE id = :id"
            ),
            {"body": ch.text, "id": chunk.id},
        )

    if version.is_active:
        version.processing_status = ProcessingStatus.READY
    else:
        version.processing_status = ProcessingStatus.READY
    doc.updated_at = datetime.now(UTC)
    await db.flush()
    return {
        "document_id": str(document_id),
        "version_id": str(version_id),
        "chunk_count": len(chunks),
        "status": "reindexed",
    }
