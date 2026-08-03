# API Documentation — Phase 4

OpenAPI from FastAPI is available at `/docs` when the backend is running.

## Versioning

| Surface | Path | Versioned |
|---------|------|-----------|
| Business APIs | `/api/v1/...` | Yes |
| Liveness | `/health` | No |
| Readiness | `/ready` | No |

## Demo authentication (not production)

- Header `X-Demo-User-Key: demo-anya` (or `demo-rahul`, `demo-priya`, `demo-arjun`)
- Optional: `Idempotency-Key` for state-changing tool paths.

## Chat

`POST /api/v1/chat/messages` — controlled workflow (tools + hybrid RAG). Unchanged from Phase 3 for text.

## Knowledge

See Phase 3 routes under `/api/v1/knowledge/...`.

## Voice (`/api/v1/voice`)

Voice is a transport into the existing orchestrator. Default STT/TTS are **deterministic mocks**.

| Method | Path | Notes |
|--------|------|-------|
| POST | `/voice/upload` | multipart audio; validates type/size/duration |
| POST | `/voice/messages/{id}/transcribe` | mock STT; optional auto-submit when confidence high and not sensitive |
| GET | `/voice/messages/{id}` | status + transcript metadata |
| POST | `/voice/messages/{id}/confirm` | bind transcript hash |
| POST | `/voice/messages/{id}/edit` | edit transcript; invalidates confirmation |
| POST | `/voice/messages/{id}/submit` | submit confirmed text to orchestrator |
| POST | `/voice/tts` | mock TTS for assistant message |
| GET | `/voice/messages/{id}/download` | authorized recording playback |
| GET | `/voice/synthesis/{id}/download` | authorized TTS playback |
| DELETE | `/voice/messages/{id}` | delete recording |
| POST | `/voice/cleanup` | expired audio cleanup |

Sensitive intents always require transcript confirmation before submit. Editing invalidates prior confirmation.
