"""Phase 4 voice APIs — thin router delegating to voice service."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_demo_user, get_request_id
from app.database.session import get_db
from app.models import User
from app.schemas.voice import (
    SpeechSynthesisOut,
    TranscriptConfirmRequest,
    TranscriptEditRequest,
    TTSRequest,
    VoiceCleanupResponse,
    VoiceDeleteResponse,
    VoiceStatusResponse,
    VoiceSubmitResponse,
    VoiceUploadResponse,
)
from app.services import voice as voice_service

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/upload", response_model=VoiceUploadResponse)
async def upload_voice(
    file: UploadFile = File(...),
    conversation_id: UUID | None = Form(default=None),
    requested_language: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> VoiceUploadResponse:
    data = await file.read()
    mime = file.content_type or "application/octet-stream"
    return await voice_service.upload_voice(
        db=db,
        user=user,
        data=data,
        mime_type=mime,
        filename=file.filename,
        conversation_id=conversation_id,
        requested_language=requested_language,
        request_id=request_id,
    )


@router.post("/messages/{voice_message_id}/transcribe", response_model=None)
async def transcribe_voice(
    voice_message_id: UUID,
    mock_mode: str | None = Query(default=None),
    fixture_key: str | None = Query(default=None),
    auto_submit: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> VoiceStatusResponse | VoiceSubmitResponse:
    return await voice_service.transcribe_voice(
        db=db,
        user=user,
        voice_message_id=voice_message_id,
        request_id=request_id,
        mock_mode=mock_mode,
        fixture_key=fixture_key,
        auto_submit=auto_submit,
    )


@router.get("/messages/{voice_message_id}", response_model=VoiceStatusResponse)
async def get_voice_status(
    voice_message_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> VoiceStatusResponse:
    return await voice_service.get_voice_status(
        db=db,
        user=user,
        voice_message_id=voice_message_id,
        request_id=request_id,
    )


@router.post("/messages/{voice_message_id}/confirm", response_model=VoiceStatusResponse)
async def confirm_transcript(
    voice_message_id: UUID,
    payload: TranscriptConfirmRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> VoiceStatusResponse:
    return await voice_service.confirm_transcript(
        db=db,
        user=user,
        voice_message_id=voice_message_id,
        transcript_hash=payload.transcript_hash,
        request_id=request_id,
    )


@router.post("/messages/{voice_message_id}/edit", response_model=VoiceStatusResponse)
async def edit_transcript(
    voice_message_id: UUID,
    payload: TranscriptEditRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> VoiceStatusResponse:
    return await voice_service.edit_transcript(
        db=db,
        user=user,
        voice_message_id=voice_message_id,
        transcript=payload.transcript,
        request_id=request_id,
    )


@router.post("/messages/{voice_message_id}/submit", response_model=VoiceSubmitResponse)
async def submit_transcript(
    voice_message_id: UUID,
    transcript_hash: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> VoiceSubmitResponse:
    return await voice_service.submit_transcript(
        db=db,
        user=user,
        voice_message_id=voice_message_id,
        request_id=request_id,
        idempotency_key=idempotency_key,
        transcript_hash=transcript_hash,
        auto=False,
    )


@router.post("/tts", response_model=SpeechSynthesisOut)
async def request_tts(
    payload: TTSRequest,
    mock_mode: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> SpeechSynthesisOut:
    return await voice_service.synthesize_speech(
        db=db,
        user=user,
        message_id=payload.message_id,
        request_id=request_id,
        language=payload.language,
        voice_name=payload.voice_name,
        mock_mode=mock_mode,
    )


@router.get("/messages/{voice_message_id}/download")
async def download_voice_recording(
    voice_message_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> Response:
    data, mime = await voice_service.read_authorized_audio(
        db=db,
        user=user,
        request_id=request_id,
        voice_message_id=voice_message_id,
    )
    return Response(content=data, media_type=mime)


@router.get("/synthesis/{synthesis_id}/download")
async def download_synthesized_audio(
    synthesis_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> Response:
    data, mime = await voice_service.read_authorized_audio(
        db=db,
        user=user,
        request_id=request_id,
        synthesis_id=synthesis_id,
    )
    return Response(content=data, media_type=mime)


@router.delete("/messages/{voice_message_id}", response_model=VoiceDeleteResponse)
async def delete_voice_message(
    voice_message_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> VoiceDeleteResponse:
    return await voice_service.delete_voice_message(
        db=db,
        user=user,
        voice_message_id=voice_message_id,
        request_id=request_id,
    )


@router.post("/cleanup", response_model=VoiceCleanupResponse)
async def cleanup_expired_audio(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_demo_user),
    request_id: str = Depends(get_request_id),
) -> VoiceCleanupResponse:
    return await voice_service.cleanup_expired_audio(
        db=db,
        user=user,
        request_id=request_id,
    )
