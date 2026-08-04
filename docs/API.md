# VaaniDesk — API Reference

Base URL: `http://localhost:8000` (development) or your production domain.

All versioned endpoints live under `/api/v1`.

## Authentication

### POST /api/v1/auth/register
Create a new user account.

**Body:** `{ "email": "user@example.com", "password": "min8chars", "display_name": "Name" }`
**Response:** `201` with `UserProfile`

### POST /api/v1/auth/login
Authenticate and receive tokens.

**Body:** `{ "email": "user@example.com", "password": "password" }`
**Response:** `200` with `{ "access_token": "...", "token_type": "bearer", "expires_in": 900 }`
**Cookie:** `refresh_token` (HttpOnly, Secure in production)

### POST /api/v1/auth/refresh
Rotate refresh token and get new access token.

**Cookie required:** `refresh_token`
**Response:** `200` with new `TokenResponse`

### POST /api/v1/auth/logout
Revoke current refresh session.

**Headers:** `Authorization: Bearer <token>`
**Response:** `204`

### POST /api/v1/auth/logout-all
Revoke all refresh sessions.

**Headers:** `Authorization: Bearer <token>`
**Response:** `204`

### GET /api/v1/auth/me
Get current user profile.

**Headers:** `Authorization: Bearer <token>`
**Response:** `200` with `UserProfile`

### POST /api/v1/auth/password
Change password (invalidates all sessions).

**Headers:** `Authorization: Bearer <token>`
**Body:** `{ "current_password": "old", "new_password": "new8chars" }`
**Response:** `204`

### GET /api/v1/auth/sessions
List active refresh sessions.

**Headers:** `Authorization: Bearer <token>`
**Response:** `200` with `SessionInfo[]`

### DELETE /api/v1/auth/sessions/{session_id}
Revoke a specific session.

**Headers:** `Authorization: Bearer <token>`
**Response:** `204`

## Chat

### POST /api/v1/chat/messages
Send a message and receive AI response.

### POST /api/v1/actions/confirm
Confirm or deny a pending action.

### GET /api/v1/conversations
List user conversations.

### GET /api/v1/conversations/{id}
Get conversation detail with messages.

## Knowledge

### GET /api/v1/knowledge/documents
List knowledge documents.

### POST /api/v1/knowledge/documents
Ingest a new document.

### POST /api/v1/knowledge/retrieval/test
Test retrieval against knowledge base.

## Voice

### POST /api/v1/voice/upload
Upload audio file for transcription.

### POST /api/v1/voice/messages/{id}/transcribe
Trigger STT transcription.

### POST /api/v1/voice/tts
Request text-to-speech synthesis.

## Channels

### GET /api/v1/channels/connections
List channel connections.

### POST /api/v1/channels/simulator/email
Simulate inbound email event.

### POST /api/v1/channels/simulator/whatsapp
Simulate inbound WhatsApp event.

## Evaluations

### GET /api/v1/evaluations/datasets
List evaluation datasets.

### POST /api/v1/evaluations/runs
Trigger evaluation run.

## Operations

### GET /health
Liveness check.

### GET /ready
Readiness check (DB + Redis).

### GET /metrics
Prometheus-compatible metrics.

## Error Format

All errors return:
```json
{
  "error": {
    "code": "error_code",
    "message": "Human-readable message",
    "request_id": "uuid"
  }
}
```

## Authentication Methods

1. **Bearer token** (production): `Authorization: Bearer <access_token>`
2. **Demo header** (development only, when `DEMO_MODE=true`): `X-Demo-User-Key: demo-anya`
