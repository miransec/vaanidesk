"""Voice service — upload, transcribe, confirm, submit, TTS, playback auth."""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.intent import Intent
from app.agents.language import get_language_detector
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models import (
    Conversation,
    Message,
    MessageRole,
    SpeechSynthesis,
    SpeechSynthesisStatus,
    User,
    VoiceMessage,
    VoiceTrace,
    VoiceTraceOperation,
    VoiceTraceResultStatus,
    VoiceTranscriptionStatus,
)
from app.schemas.chat import CitationOut, ConfirmationOut, MessageOut, ProviderMetadata, WorkflowOut
from app.schemas.voice import (
    SpeechSynthesisOut,
    VoiceCleanupResponse,
    VoiceDeleteResponse,
    VoiceMessageOut,
    VoiceProviderOut,
    VoiceStatusResponse,
    VoiceSubmitResponse,
    VoiceUploadResponse,
)
from app.voice.rate_limit import check_stt_limit, check_tts_limit, check_upload_limits
from app.voice.storage import AudioStorage, get_audio_storage
from app.voice.stt import MOCK_DISCLAIMER, get_stt_provider
from app.voice.tts import MOCK_TTS_DISCLAIMER, get_tts_provider
from app.voice.validation import validate_audio_upload
from app.workflows.orchestrator import run_support_workflow
from app.workflows.types import WorkflowResult

logger = logging.getLogger(__name__)

SENSITIVE_INTENTS = frozenset(
    {
        Intent.CANCEL_ORDER,
        Intent.UPDATE_DELIVERY_ADDRESS,
    }
)


def normalize_transcript(text: str) -> str:
    return " ".join(text.strip().split())


def compute_transcript_hash(text: str) -> str:
    return hashlib.sha256(normalize_transcript(text).encode("utf-8")).hexdigest()


def _voice_provider_meta() -> VoiceProviderOut:
    return VoiceProviderOut(
        provider="mock-stt-deterministic",
        is_mock=True,
        disclaimer=MOCK_DISCLAIMER,
    )


def _is_sensitive_transcript(text: str) -> bool:
    language = get_language_detector().detect(text)
    from app.agents.intent import get_intent_classifier

    intent = get_intent_classifier().classify(text, language)
    return intent.intent in SENSITIVE_INTENTS


def _can_auto_submit(*, vm: VoiceMessage, settings: Settings) -> bool:
    if not settings.voice_auto_submit_enabled:
        return False
    if vm.transcript is None or vm.transcript_confidence is None:
        return False
    if float(vm.transcript_confidence) < settings.stt_min_auto_submit_confidence:
        return False
    return not _is_sensitive_transcript(vm.transcript)


def _voice_message_out(vm: VoiceMessage, settings: Settings) -> VoiceMessageOut:
    sensitive = bool(vm.transcript and _is_sensitive_transcript(vm.transcript))
    can_auto = _can_auto_submit(vm=vm, settings=settings) and not sensitive
    requires_confirm = sensitive or (
        vm.transcript_confirmed_at is None and not vm.auto_submitted and vm.transcript is not None
    )
    if can_auto and not sensitive:
        requires_confirm = False
    return VoiceMessageOut(
        id=vm.id,
        conversation_id=vm.conversation_id,
        user_id=vm.user_id,
        message_id=vm.message_id,
        requested_language=vm.requested_language,
        detected_language=vm.detected_language,
        original_filename=vm.original_filename,
        mime_type=vm.mime_type,
        audio_format=vm.audio_format,
        duration_ms=vm.duration_ms,
        size_bytes=vm.size_bytes,
        content_hash=vm.content_hash,
        transcription_status=vm.transcription_status.value,
        transcript=vm.transcript,
        transcript_confidence=float(vm.transcript_confidence)
        if vm.transcript_confidence is not None
        else None,
        transcript_hash=vm.transcript_hash,
        transcript_confirmed_at=vm.transcript_confirmed_at,
        submitted_at=vm.submitted_at,
        auto_submitted=vm.auto_submitted,
        requires_transcript_confirmation=requires_confirm and vm.submitted_at is None,
        can_auto_submit=can_auto,
        error_code=vm.error_code,
        created_at=vm.created_at,
        updated_at=vm.updated_at,
    )


async def _trace(
    *,
    db: AsyncSession,
    request_id: str,
    user_id: UUID,
    operation: VoiceTraceOperation,
    result_status: VoiceTraceResultStatus,
    conversation_id: UUID | None = None,
    voice_message_id: UUID | None = None,
    provider: str | None = None,
    language: str | None = None,
    latency_ms: int | None = None,
    confidence: float | None = None,
    error_code: str | None = None,
    safe_metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        VoiceTrace(
            request_id=request_id,
            user_id=user_id,
            conversation_id=conversation_id,
            voice_message_id=voice_message_id,
            operation=operation,
            provider=provider,
            language=language,
            latency_ms=latency_ms,
            confidence=confidence,
            result_status=result_status,
            error_code=error_code,
            safe_metadata=safe_metadata,
        )
    )


async def _get_owned_voice_message(
    *, db: AsyncSession, user: User, voice_message_id: UUID
) -> VoiceMessage:
    vm = await db.get(VoiceMessage, voice_message_id)
    if vm is None:
        raise AppError(code="voice_not_found", message="Voice message not found.", status_code=404)
    if vm.user_id != user.id:
        raise AppError(
            code="voice_forbidden",
            message="You cannot access another user's voice recording.",
            status_code=403,
        )
    return vm


async def _resolve_conversation(
    *,
    db: AsyncSession,
    user: User,
    conversation_id: UUID | None,
) -> Conversation:
    if conversation_id is None:
        conversation = Conversation(user_id=user.id, title="Voice conversation")
        db.add(conversation)
        await db.flush()
        return conversation
    found = await db.get(Conversation, conversation_id)
    if found is None:
        raise AppError(
            code="conversation_not_found", message="Conversation not found.", status_code=404
        )
    if found.user_id != user.id:
        raise AppError(
            code="conversation_forbidden",
            message="You cannot access another user's conversation.",
            status_code=403,
        )
    return found


def _workflow_out(result: WorkflowResult) -> WorkflowOut:
    confirmation = None
    if result.confirmation is not None:
        confirmation = ConfirmationOut(
            token=result.confirmation.token,
            action=result.confirmation.action,
            summary=result.confirmation.summary,
            expires_at=result.confirmation.expires_at,
        )
    return WorkflowOut(
        status=result.status.value,
        detected_language=result.language_code,
        script=result.script,
        intent=result.intent,
        intent_confidence=result.intent_confidence,
        selected_tool=result.selected_tool,
        tool_execution_status=result.tool_execution_status,
        clarification_required=result.clarification_required,
        confirmation_required=result.confirmation_required,
        escalation_required=result.escalation_required,
        escalation_reason=result.escalation_reason,
        trace_id=result.trace_id,
        confirmation=confirmation,
        citations=[CitationOut.model_validate(c) for c in result.citations],
        retrieval_strategy=result.retrieval_strategy,
        retrieval_confidence=result.retrieval_confidence,
        no_answer=result.no_answer,
        no_answer_reason=result.no_answer_reason,
        retrieval_trace_id=result.retrieval_trace_id,
        suspicious_evidence=result.suspicious_evidence,
    )


async def upload_voice(
    *,
    db: AsyncSession,
    user: User,
    data: bytes,
    mime_type: str,
    filename: str | None,
    conversation_id: UUID | None,
    requested_language: str | None,
    request_id: str,
    storage: AudioStorage | None = None,
    settings: Settings | None = None,
) -> VoiceUploadResponse:
    cfg = settings or get_settings()
    if not cfg.voice_enabled:
        raise AppError(
            code="voice_disabled", message="Voice features are disabled.", status_code=503
        )

    validated = validate_audio_upload(
        data=data, mime_type=mime_type, filename=filename, settings=cfg
    )
    await check_upload_limits(user_id=str(user.id), size_bytes=validated.size_bytes, settings=cfg)

    conversation = await _resolve_conversation(db=db, user=user, conversation_id=conversation_id)
    store = storage or get_audio_storage(cfg)
    stored = await store.save(
        data=validated.data,
        extension=validated.audio_format,
        owner_user_id=str(user.id),
        metadata={"mime_type": validated.mime_type, "original_filename": filename},
    )

    vm = VoiceMessage(
        conversation_id=conversation.id,
        user_id=user.id,
        requested_language=requested_language,
        original_filename=filename,
        mime_type=validated.mime_type,
        audio_format=validated.audio_format,
        duration_ms=validated.duration_ms,
        size_bytes=stored.size_bytes,
        content_hash=stored.content_hash,
        storage_reference=stored.storage_reference,
        transcription_status=VoiceTranscriptionStatus.PENDING,
    )
    db.add(vm)
    await _trace(
        db=db,
        request_id=request_id,
        user_id=user.id,
        conversation_id=conversation.id,
        voice_message_id=vm.id,
        operation=VoiceTraceOperation.UPLOAD,
        result_status=VoiceTraceResultStatus.SUCCESS,
        provider="local-audio-storage",
        safe_metadata={
            "size_bytes": stored.size_bytes,
            "audio_format": validated.audio_format,
            "content_hash_prefix": stored.content_hash[:8],
        },
    )
    await db.commit()
    await db.refresh(vm)
    return VoiceUploadResponse(
        request_id=request_id,
        voice_message=_voice_message_out(vm, cfg),
        provider=_voice_provider_meta(),
    )


async def transcribe_voice(
    *,
    db: AsyncSession,
    user: User,
    voice_message_id: UUID,
    request_id: str,
    mock_mode: str | None = None,
    fixture_key: str | None = None,
    auto_submit: bool = True,
    settings: Settings | None = None,
) -> VoiceStatusResponse | VoiceSubmitResponse:
    cfg = settings or get_settings()
    if not cfg.voice_enabled:
        raise AppError(
            code="voice_disabled", message="Voice features are disabled.", status_code=503
        )

    vm = await _get_owned_voice_message(db=db, user=user, voice_message_id=voice_message_id)
    await check_stt_limit(user_id=str(user.id), settings=cfg)

    if vm.transcription_status == VoiceTranscriptionStatus.CONFIRMED and vm.submitted_at:
        return VoiceStatusResponse(
            request_id=request_id,
            voice_message=_voice_message_out(vm, cfg),
            provider=_voice_provider_meta(),
        )

    vm.transcription_status = VoiceTranscriptionStatus.PROCESSING
    await db.flush()

    storage = get_audio_storage(cfg)
    started = time.perf_counter()
    try:
        audio_bytes = await storage.read(vm.storage_reference)
        stt = get_stt_provider(cfg)
        result = await stt.transcribe(
            audio_bytes=audio_bytes,
            content_hash=vm.content_hash,
            requested_language=vm.requested_language,
            fixture_key=fixture_key,
            mock_mode=mock_mode,
        )
        vm.transcript = result.transcript
        vm.detected_language = result.detected_language
        vm.transcript_confidence = result.confidence
        vm.transcript_hash = compute_transcript_hash(result.transcript)
        vm.transcription_status = VoiceTranscriptionStatus.COMPLETED
        vm.error_code = None
        vm.error_message = None
        vm.provider_metadata = {
            "stt_provider": result.provider,
            "is_mock": result.is_mock,
            "fixture_key": result.metadata.get("fixture_key"),
        }
        latency = int((time.perf_counter() - started) * 1000)
        await _trace(
            db=db,
            request_id=request_id,
            user_id=user.id,
            conversation_id=vm.conversation_id,
            voice_message_id=vm.id,
            operation=VoiceTraceOperation.TRANSCRIBE,
            result_status=VoiceTraceResultStatus.SUCCESS,
            provider=result.provider,
            language=result.detected_language,
            latency_ms=latency,
            confidence=result.confidence,
            safe_metadata={"content_hash_prefix": vm.content_hash[:8]},
        )
        await db.commit()
        await db.refresh(vm)

        if auto_submit and _can_auto_submit(vm=vm, settings=cfg):
            return await submit_transcript(
                db=db,
                user=user,
                voice_message_id=vm.id,
                request_id=request_id,
                idempotency_key=None,
                settings=cfg,
                auto=True,
            )
    except AppError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        status = (
            VoiceTraceResultStatus.TIMEOUT
            if exc.code == "stt_timeout"
            else VoiceTraceResultStatus.FAILURE
        )
        vm.transcription_status = VoiceTranscriptionStatus.FAILED
        vm.error_code = exc.code
        vm.error_message = exc.message
        await _trace(
            db=db,
            request_id=request_id,
            user_id=user.id,
            conversation_id=vm.conversation_id,
            voice_message_id=vm.id,
            operation=VoiceTraceOperation.TRANSCRIBE,
            result_status=status,
            provider="mock-stt-deterministic",
            latency_ms=latency,
            error_code=exc.code,
        )
        await db.commit()
        raise

    return VoiceStatusResponse(
        request_id=request_id,
        voice_message=_voice_message_out(vm, cfg),
        provider=_voice_provider_meta(),
    )


async def get_voice_status(
    *,
    db: AsyncSession,
    user: User,
    voice_message_id: UUID,
    request_id: str,
    settings: Settings | None = None,
) -> VoiceStatusResponse:
    cfg = settings or get_settings()
    vm = await _get_owned_voice_message(db=db, user=user, voice_message_id=voice_message_id)
    return VoiceStatusResponse(
        request_id=request_id,
        voice_message=_voice_message_out(vm, cfg),
        provider=_voice_provider_meta(),
    )


async def confirm_transcript(
    *,
    db: AsyncSession,
    user: User,
    voice_message_id: UUID,
    transcript_hash: str,
    request_id: str,
    settings: Settings | None = None,
) -> VoiceStatusResponse:
    cfg = settings or get_settings()
    vm = await _get_owned_voice_message(db=db, user=user, voice_message_id=voice_message_id)
    if not vm.transcript:
        raise AppError(
            code="transcript_missing",
            message="No transcript available to confirm.",
            status_code=400,
        )
    current_hash = compute_transcript_hash(vm.transcript)
    if transcript_hash != current_hash:
        raise AppError(
            code="transcript_hash_mismatch",
            message="Transcript hash does not match the current transcript.",
            status_code=409,
        )
    if vm.submitted_at is not None:
        raise AppError(
            code="transcript_already_submitted",
            message="Transcript was already submitted to the workflow.",
            status_code=409,
        )

    vm.transcript_confirmed_at = datetime.now(UTC)
    vm.transcription_status = VoiceTranscriptionStatus.CONFIRMED
    await _trace(
        db=db,
        request_id=request_id,
        user_id=user.id,
        conversation_id=vm.conversation_id,
        voice_message_id=vm.id,
        operation=VoiceTraceOperation.CONFIRM,
        result_status=VoiceTraceResultStatus.SUCCESS,
        safe_metadata={"transcript_hash_prefix": transcript_hash[:8]},
    )
    await db.commit()
    await db.refresh(vm)
    return VoiceStatusResponse(
        request_id=request_id,
        voice_message=_voice_message_out(vm, cfg),
        provider=_voice_provider_meta(),
    )


async def edit_transcript(
    *,
    db: AsyncSession,
    user: User,
    voice_message_id: UUID,
    transcript: str,
    request_id: str,
    settings: Settings | None = None,
) -> VoiceStatusResponse:
    cfg = settings or get_settings()
    vm = await _get_owned_voice_message(db=db, user=user, voice_message_id=voice_message_id)
    if vm.submitted_at is not None:
        raise AppError(
            code="transcript_already_submitted",
            message="Cannot edit a transcript that was already submitted.",
            status_code=409,
        )

    normalized = normalize_transcript(transcript)
    vm.transcript = normalized
    vm.transcript_hash = compute_transcript_hash(normalized)
    vm.transcript_confirmed_at = None
    vm.transcription_status = VoiceTranscriptionStatus.COMPLETED
    vm.auto_submitted = False
    await _trace(
        db=db,
        request_id=request_id,
        user_id=user.id,
        conversation_id=vm.conversation_id,
        voice_message_id=vm.id,
        operation=VoiceTraceOperation.EDIT,
        result_status=VoiceTraceResultStatus.SUCCESS,
        safe_metadata={"transcript_hash_prefix": vm.transcript_hash[:8]},
    )
    await db.commit()
    await db.refresh(vm)
    return VoiceStatusResponse(
        request_id=request_id,
        voice_message=_voice_message_out(vm, cfg),
        provider=_voice_provider_meta(),
    )


async def submit_transcript(
    *,
    db: AsyncSession,
    user: User,
    voice_message_id: UUID,
    request_id: str,
    idempotency_key: str | None = None,
    transcript_hash: str | None = None,
    settings: Settings | None = None,
    auto: bool = False,
) -> VoiceSubmitResponse:
    cfg = settings or get_settings()
    vm = await _get_owned_voice_message(db=db, user=user, voice_message_id=voice_message_id)

    if vm.submitted_at is not None:
        raise AppError(
            code="transcript_replay_rejected",
            message="This voice transcript was already submitted.",
            status_code=409,
        )
    if not vm.transcript:
        raise AppError(
            code="transcript_missing", message="Transcript is required.", status_code=400
        )

    current_hash = compute_transcript_hash(vm.transcript)
    if transcript_hash and transcript_hash != current_hash:
        raise AppError(
            code="transcript_hash_mismatch",
            message="Submitted transcript hash does not match.",
            status_code=409,
        )

    sensitive = _is_sensitive_transcript(vm.transcript)
    if sensitive and vm.transcript_confirmed_at is None:
        raise AppError(
            code="transcript_confirmation_required",
            message="Sensitive voice intents require explicit transcript confirmation.",
            status_code=403,
        )
    if not auto:
        if sensitive and vm.transcript_confirmed_at is None:
            raise AppError(
                code="transcript_confirmation_required",
                message="Confirm the transcript before submitting sensitive requests.",
                status_code=403,
            )
        if (
            not sensitive
            and vm.transcript_confirmed_at is None
            and not _can_auto_submit(vm=vm, settings=cfg)
        ):
            raise AppError(
                code="transcript_confirmation_required",
                message="Confirm or edit the transcript before submitting.",
                status_code=403,
            )
    elif not _can_auto_submit(vm=vm, settings=cfg):
        raise AppError(
            code="auto_submit_not_allowed",
            message="Auto-submit is not allowed for this transcript.",
            status_code=403,
        )

    user_message = Message(
        conversation_id=vm.conversation_id,
        role=MessageRole.USER,
        content=vm.transcript,
        request_id=request_id,
        provider_metadata={
            "source": "voice",
            "voice_message_id": str(vm.id),
            "transcript_hash": current_hash,
            "is_mock_stt": True,
        },
    )
    db.add(user_message)
    await db.flush()

    result = await run_support_workflow(
        db=db,
        user=user,
        conversation_id=vm.conversation_id,
        message_id=user_message.id,
        text=vm.transcript,
        request_id=request_id,
        idempotency_key=idempotency_key,
    )

    assistant_message = Message(
        conversation_id=vm.conversation_id,
        role=MessageRole.ASSISTANT,
        content=result.assistant_text,
        request_id=request_id,
        provider_metadata={
            "workflow_status": result.status.value,
            "intent": result.intent,
            "trace_id": str(result.trace_id) if result.trace_id else None,
            "source": "voice_orchestrator",
            "is_mock": True,
        },
    )
    db.add(assistant_message)

    conversation = await db.get(Conversation, vm.conversation_id)
    if conversation:
        conversation.updated_at = datetime.now(UTC)

    vm.message_id = user_message.id
    vm.submitted_at = datetime.now(UTC)
    vm.auto_submitted = auto
    if vm.transcript_confirmed_at is None and not sensitive:
        vm.transcript_confirmed_at = datetime.now(UTC)
        vm.transcription_status = VoiceTranscriptionStatus.CONFIRMED

    await _trace(
        db=db,
        request_id=request_id,
        user_id=user.id,
        conversation_id=vm.conversation_id,
        voice_message_id=vm.id,
        operation=VoiceTraceOperation.SUBMIT,
        result_status=VoiceTraceResultStatus.SUCCESS,
        provider="workflow-heuristic",
        language=result.language_code,
        safe_metadata={
            "transcript_hash_prefix": current_hash[:8],
            "intent": result.intent,
            "auto_submitted": auto,
        },
    )
    await db.commit()
    await db.refresh(vm)
    await db.refresh(user_message)
    await db.refresh(assistant_message)

    provider = ProviderMetadata(
        provider="workflow-heuristic",
        model="vaanidesk-phase4-voice-workflow",
        is_mock=True,
        language_hint=result.language_code,
        disclaimer="Voice submitted through controlled orchestrator — mock STT/TTS",
    )
    return VoiceSubmitResponse(
        request_id=request_id,
        voice_message=_voice_message_out(vm, cfg),
        conversation_id=vm.conversation_id,
        user_message=MessageOut.model_validate(user_message),
        assistant_message=MessageOut.model_validate(assistant_message),
        provider=provider,
        workflow=_workflow_out(result),
    )


async def synthesize_speech(
    *,
    db: AsyncSession,
    user: User,
    message_id: UUID,
    request_id: str,
    language: str | None = None,
    voice_name: str | None = None,
    mock_mode: str | None = None,
    settings: Settings | None = None,
) -> SpeechSynthesisOut:
    cfg = settings or get_settings()
    if not cfg.voice_enabled:
        raise AppError(
            code="voice_disabled", message="Voice features are disabled.", status_code=503
        )

    message = await db.get(Message, message_id)
    if message is None:
        raise AppError(code="message_not_found", message="Message not found.", status_code=404)
    conversation = await db.get(Conversation, message.conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise AppError(
            code="message_forbidden",
            message="You cannot synthesize audio for this message.",
            status_code=403,
        )

    await check_tts_limit(user_id=str(user.id), settings=cfg)
    lang = language or "en"
    synth = SpeechSynthesis(
        message_id=message.id,
        user_id=user.id,
        language=lang,
        provider="mock-tts-deterministic",
        voice_name=voice_name,
        status=SpeechSynthesisStatus.PROCESSING,
        expires_at=datetime.now(UTC) + timedelta(hours=cfg.audio_retention_hours),
    )
    db.add(synth)
    await db.flush()

    started = time.perf_counter()
    try:
        tts = get_tts_provider(cfg)
        result = await tts.synthesize(
            text=message.content,
            language=lang,
            voice_name=voice_name,
            mock_mode=mock_mode,
        )
        storage = get_audio_storage(cfg)
        stored = await storage.save(
            data=result.audio_bytes,
            extension=result.audio_format,
            owner_user_id=str(user.id),
            metadata={"message_id": str(message.id), "synthesis_id": str(synth.id)},
        )
        synth.storage_reference = stored.storage_reference
        synth.content_hash = stored.content_hash
        synth.size_bytes = stored.size_bytes
        synth.duration_ms = result.duration_ms
        synth.status = SpeechSynthesisStatus.COMPLETED
        latency = int((time.perf_counter() - started) * 1000)
        await _trace(
            db=db,
            request_id=request_id,
            user_id=user.id,
            conversation_id=conversation.id,
            operation=VoiceTraceOperation.TTS,
            result_status=VoiceTraceResultStatus.SUCCESS,
            provider=result.provider,
            language=lang,
            latency_ms=latency,
            safe_metadata={"content_hash_prefix": stored.content_hash[:8]},
        )
    except AppError as exc:
        synth.status = SpeechSynthesisStatus.FAILED
        synth.error_code = exc.code
        status = (
            VoiceTraceResultStatus.TIMEOUT
            if exc.code == "tts_timeout"
            else VoiceTraceResultStatus.FAILURE
        )
        await _trace(
            db=db,
            request_id=request_id,
            user_id=user.id,
            conversation_id=conversation.id,
            operation=VoiceTraceOperation.TTS,
            result_status=status,
            provider="mock-tts-deterministic",
            error_code=exc.code,
        )
        await db.commit()
        raise

    await db.commit()
    await db.refresh(synth)
    return _synthesis_out(synth, cfg)


def _synthesis_out(synth: SpeechSynthesis, settings: Settings) -> SpeechSynthesisOut:
    prefix = settings.api_prefix.rstrip("/")
    download_url = f"{prefix}/voice/synthesis/{synth.id}/download"
    return SpeechSynthesisOut(
        id=synth.id,
        message_id=synth.message_id,
        user_id=synth.user_id,
        language=synth.language,
        provider=synth.provider,
        voice_name=synth.voice_name,
        audio_format=synth.audio_format,
        duration_ms=synth.duration_ms,
        size_bytes=synth.size_bytes,
        content_hash=synth.content_hash,
        status=synth.status.value,
        download_url=download_url,
        expires_at=synth.expires_at,
        is_mock=True,
        disclaimer=MOCK_TTS_DISCLAIMER,
        created_at=synth.created_at,
    )


async def authorize_playback(
    *,
    db: AsyncSession,
    user: User,
    voice_message_id: UUID | None = None,
    synthesis_id: UUID | None = None,
) -> tuple[str, str]:
    if voice_message_id is not None:
        vm = await _get_owned_voice_message(db=db, user=user, voice_message_id=voice_message_id)
        return vm.storage_reference, vm.mime_type
    if synthesis_id is not None:
        synth = await db.get(SpeechSynthesis, synthesis_id)
        if synth is None:
            raise AppError(
                code="synthesis_not_found", message="Synthesis not found.", status_code=404
            )
        if synth.user_id != user.id:
            raise AppError(
                code="synthesis_forbidden",
                message="You cannot access another user's synthesized audio.",
                status_code=403,
            )
        if synth.status != SpeechSynthesisStatus.COMPLETED or not synth.storage_reference:
            raise AppError(
                code="synthesis_not_ready",
                message="Synthesized audio is not ready.",
                status_code=404,
            )
        if synth.expires_at and synth.expires_at < datetime.now(UTC):
            synth.status = SpeechSynthesisStatus.EXPIRED
            await db.commit()
            raise AppError(
                code="synthesis_expired",
                message="Synthesized audio has expired.",
                status_code=410,
            )
        return synth.storage_reference, "audio/wav"
    raise AppError(
        code="playback_target_missing",
        message="Specify voice_message_id or synthesis_id.",
        status_code=400,
    )


async def read_authorized_audio(
    *,
    db: AsyncSession,
    user: User,
    request_id: str,
    voice_message_id: UUID | None = None,
    synthesis_id: UUID | None = None,
    storage: AudioStorage | None = None,
) -> tuple[bytes, str]:
    ref, mime = await authorize_playback(
        db=db,
        user=user,
        voice_message_id=voice_message_id,
        synthesis_id=synthesis_id,
    )
    store = storage or get_audio_storage()
    data = await store.read(ref)
    await _trace(
        db=db,
        request_id=request_id,
        user_id=user.id,
        operation=VoiceTraceOperation.DOWNLOAD,
        result_status=VoiceTraceResultStatus.SUCCESS,
        safe_metadata={"storage_ref_prefix": ref[:16]},
    )
    await db.commit()
    return data, mime


async def delete_voice_message(
    *,
    db: AsyncSession,
    user: User,
    voice_message_id: UUID,
    request_id: str,
    storage: AudioStorage | None = None,
) -> VoiceDeleteResponse:
    vm = await _get_owned_voice_message(db=db, user=user, voice_message_id=voice_message_id)
    store = storage or get_audio_storage()
    await store.delete(vm.storage_reference)
    await _trace(
        db=db,
        request_id=request_id,
        user_id=user.id,
        conversation_id=vm.conversation_id,
        voice_message_id=vm.id,
        operation=VoiceTraceOperation.DELETE,
        result_status=VoiceTraceResultStatus.SUCCESS,
    )
    await db.delete(vm)
    await db.commit()
    return VoiceDeleteResponse(
        request_id=request_id,
        deleted=True,
        voice_message_id=voice_message_id,
    )


async def cleanup_expired_audio(
    *,
    db: AsyncSession,
    user: User,
    request_id: str,
    storage: AudioStorage | None = None,
    settings: Settings | None = None,
) -> VoiceCleanupResponse:
    cfg = settings or get_settings()
    store = storage or get_audio_storage(cfg)
    removed = await store.cleanup_expired(retention_hours=cfg.audio_retention_hours)
    await _trace(
        db=db,
        request_id=request_id,
        user_id=user.id,
        operation=VoiceTraceOperation.CLEANUP,
        result_status=VoiceTraceResultStatus.SUCCESS,
        safe_metadata={"removed_files": removed},
    )
    await db.commit()
    return VoiceCleanupResponse(request_id=request_id, removed_files=removed)
