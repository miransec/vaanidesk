# API Documentation — Phase 3

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

## Chat

### `POST /api/v1/chat/messages`

Runs the controlled workflow. Policy questions use **hybrid retrieval** (not tools). Order-status questions still use structured tools.

Workflow extras for RAG:

```json
{
  "workflow": {
    "intent": "policy_question",
    "retrieval_strategy": "hybrid",
    "retrieval_confidence": 0.82,
    "no_answer": false,
    "citations": [
      {
        "document_title": "VaaniDesk Return Procedure",
        "document_version": 2,
        "section_label": "Window",
        "chunk_id": "...",
        "source_type": "markdown",
        "score": 0.031
      }
    ],
    "retrieval_trace_id": "...",
    "suspicious_evidence": false
  }
}
```

### `POST /api/v1/actions/confirm`

Unchanged from Phase 2 (Redis fail-closed confirmation).

## Knowledge

### `POST /api/v1/knowledge/documents`

```json
{
  "title": "Shipping SLA",
  "content": "# Shipping\n\nStandard delivery is 3–5 business days.",
  "mime_type": "text/markdown",
  "language": "en",
  "access_level": "authenticated",
  "activate": true
}
```

Supported MIME: `text/markdown`, `text/plain`, `application/json` (approved text fields only).

### `GET /api/v1/knowledge/documents`

### `GET /api/v1/knowledge/documents/{id}`

Includes versions + chunk counts.

### `GET /api/v1/knowledge/documents/{id}/versions`

### `POST /api/v1/knowledge/documents/{id}/activate`

```json
{ "version_id": "..." }
```

### `POST /api/v1/knowledge/documents/{id}/deactivate`

### `POST /api/v1/knowledge/documents/{id}/versions/{version_id}/reindex`

### `POST /api/v1/knowledge/retrieval/test`

```json
{
  "query": "What is the return procedure?",
  "strategy": "hybrid",
  "top_k": 5,
  "persist_trace": true
}
```

Strategies: `keyword` | `vector` | `hybrid` | `hybrid_rerank`

### `GET /api/v1/knowledge/retrieval/traces/{trace_id}`

Own traces only. Stores IDs/scores/titles — not unauthorized chunk bodies.

## Public identifiers

| Kind | Format | Example |
|------|--------|---------|
| Order | `VD-xxxxx` | `VD-10001` |
| Ticket | `TKT-xxxxx` | `TKT-10001` |

Order lookups always require **authenticated user + public ref**.
