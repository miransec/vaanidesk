"""Phase 3 knowledge / retrieval APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_request_id
from app.database.session import get_db
from app.models import User
from app.schemas.knowledge import (
    ActivateVersionRequest,
    IngestResultOut,
    KnowledgeDocumentCreate,
    KnowledgeDocumentDetail,
    KnowledgeDocumentOut,
    KnowledgeVersionOut,
    RetrievalTestRequest,
    RetrievalTestResponse,
    RetrievalTraceOut,
)
from app.services import knowledge as knowledge_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/documents", response_model=IngestResultOut)
async def create_knowledge_document(
    payload: KnowledgeDocumentCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> IngestResultOut:
    return await knowledge_service.create_document(db=db, payload=payload)


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
async def list_knowledge_documents(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[KnowledgeDocumentOut]:
    return await knowledge_service.list_documents(db=db)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentDetail)
async def get_knowledge_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> KnowledgeDocumentDetail:
    return await knowledge_service.get_document(db=db, document_id=document_id)


@router.get("/documents/{document_id}/versions", response_model=list[KnowledgeVersionOut])
async def list_knowledge_versions(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[KnowledgeVersionOut]:
    return await knowledge_service.list_versions(db=db, document_id=document_id)


@router.post("/documents/{document_id}/activate")
async def activate_knowledge_version(
    document_id: UUID,
    payload: ActivateVersionRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await knowledge_service.activate_document_version(
        db=db, document_id=document_id, payload=payload
    )


@router.post("/documents/{document_id}/deactivate")
async def deactivate_knowledge_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await knowledge_service.deactivate_doc(db=db, document_id=document_id)


@router.post("/documents/{document_id}/versions/{version_id}/reindex")
async def reindex_knowledge_version(
    document_id: UUID,
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await knowledge_service.reindex_document_version(
        db=db, document_id=document_id, version_id=version_id
    )


@router.post("/retrieval/test", response_model=RetrievalTestResponse)
async def test_retrieval(
    payload: RetrievalTestRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    request_id: str = Depends(get_request_id),
) -> RetrievalTestResponse:
    return await knowledge_service.run_retrieval_test(
        db=db, user=user, payload=payload, request_id=request_id
    )


@router.get("/retrieval/traces/{trace_id}", response_model=RetrievalTraceOut)
async def get_retrieval_trace(
    trace_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RetrievalTraceOut:
    return await knowledge_service.get_retrieval_trace(db=db, user=user, trace_id=trace_id)
