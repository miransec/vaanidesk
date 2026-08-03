# API Documentation — Phase 1

OpenAPI from FastAPI is available at `/docs` when the backend is running.

## Versioning

| Surface | Path | Versioned |
|---------|------|-----------|
| Business APIs | `/api/v1/...` | Yes |
| Liveness | `/health` | No |
| Readiness | `/ready` | No |

## Demo authentication (Phase 1 only)

Not production-ready. Identify the demo user with one of:

- Header `X-Demo-User-Key: demo-anya` (or `demo-rahul`, `demo-priya`, `demo-arjun`)
- Header `X-Demo-User-Id: <uuid>`

Missing/invalid identity → `401` with `error.code` `demo_auth_required` or `demo_user_not_found`.

## Endpoints

### `GET /health`

Returns `{ "status": "ok", "service": "vaanidesk-backend" }`.

### `GET /ready`

Checks PostgreSQL (required) and Redis (reported). Returns `503` if PostgreSQL is unavailable. Details include exception **type names only** (no connection strings/secrets).

### `GET /api/v1/demo-users`

Lists seeded demo users for the UI.

### `POST /api/v1/chat/messages`

Request:

```json
{
  "content": "mera order kahan hai",
  "conversation_id": null
}
```

Response includes `request_id`, `conversation_id`, `user_message`, `assistant_message`, and `provider` metadata (`is_mock`, model name, language hint).

### `GET /api/v1/conversations`

Lists conversations for the authenticated demo user only.

### `GET /api/v1/conversations/{conversation_id}`

Returns messages. Another user's conversation → `403` `conversation_forbidden`.

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
