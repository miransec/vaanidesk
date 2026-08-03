# API Documentation — Phase 2

OpenAPI from FastAPI is available at `/docs` when the backend is running.

## Versioning

| Surface | Path | Versioned |
|---------|------|-----------|
| Business APIs | `/api/v1/...` | Yes |
| Liveness | `/health` | No |
| Readiness | `/ready` | No |

## Demo authentication (not production)

Identify the demo user with one of:

- Header `X-Demo-User-Key: demo-anya` (or `demo-rahul`, `demo-priya`, `demo-arjun`)
- Header `X-Demo-User-Id: <uuid>`

Optional: `Idempotency-Key` for state-changing tool paths.

## Endpoints

### `GET /health` / `GET /ready`

Unchanged from Phase 1. Postgres required for ready; Redis reported.

### `GET /api/v1/demo-users`

Lists seeded demo users.

### `POST /api/v1/chat/messages`

Runs the **controlled Phase 2 workflow** (language → intent → tools → confirm/escalate).

Request:

```json
{
  "content": "where is my order VD-10001",
  "conversation_id": null
}
```

Response (abbreviated):

```json
{
  "request_id": "...",
  "conversation_id": "...",
  "user_message": { "...": "..." },
  "assistant_message": { "...": "..." },
  "provider": {
    "provider": "workflow-heuristic",
    "model": "vaanidesk-phase2-workflow",
    "is_mock": true,
    "language_hint": "en"
  },
  "workflow": {
    "status": "completed",
    "detected_language": "en",
    "script": "latin",
    "intent": "order_status",
    "intent_confidence": 0.9,
    "selected_tool": "get_order_status",
    "tool_execution_status": "success",
    "clarification_required": false,
    "confirmation_required": false,
    "escalation_required": false,
    "trace_id": "..."
  }
}
```

When confirmation is required:

```json
{
  "workflow": {
    "status": "confirmation_required",
    "confirmation_required": true,
    "selected_tool": "cancel_order",
    "confirmation": {
      "token": "<opaque>",
      "action": "cancel_order",
      "summary": "Cancel order VD-10001",
      "expires_at": "..."
    }
  }
}
```

Do not put confirmation tokens in URLs. Tokens are never logged.

### `POST /api/v1/actions/confirm`

```json
{
  "confirmation_token": "<opaque>",
  "approved": true
}
```

- Wrong user → `403 confirmation_forbidden` (token not consumed)
- Invalid/expired/reused → `400`
- Redis down → `503 confirmation_unavailable` (fail closed)

### Conversations

`GET /api/v1/conversations` and `GET /api/v1/conversations/{id}` unchanged; ownership enforced.

## Public identifiers

| Kind | Format | Example |
|------|--------|---------|
| Order | `VD-xxxxx` | `VD-10001` |
| Ticket | `TKT-xxxxx` | `TKT-10001` |

Order lookups always require **authenticated user + public ref**. Lookup by ref alone is forbidden.

## Error envelope

```json
{
  "error": {
    "code": "conversation_forbidden",
    "message": "You cannot access another user's conversation.",
    "details": null,
    "request_id": "..."
  }
}
```

Responses also set `X-Request-ID`.
