# VaaniDesk — Architecture

## System Overview

VaaniDesk is a multilingual AI customer support platform supporting text chat, voice, and omnichannel communication (email, WhatsApp).

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Browser   │────▶│   Caddy      │────▶│   Next.js    │
│   (SPA)     │     │   (HTTPS)    │     │   Frontend   │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────▼───────┐
                    │   FastAPI    │
                    │   Backend    │
                    └──┬───────┬──┘
                       │       │
              ┌────────▼──┐  ┌─▼────────┐
              │ PostgreSQL │  │  Redis   │
              │ + pgvector │  │          │
              └───────────┘  └──────────┘
```

## Backend Architecture

### Layer Structure

```
app/
├── api/v1/          # HTTP route handlers (thin controllers)
│   ├── auth.py      # Registration, login, refresh, sessions
│   ├── chat.py      # Conversations, messages, confirmations
│   ├── knowledge.py # Document ingestion, retrieval
│   ├── voice.py     # Audio upload, STT/TTS, transcript flow
│   ├── channels.py  # Omnichannel connections, webhooks
│   └── evaluations.py # Eval datasets, runs, alerts, audit
├── services/        # Business logic layer
│   ├── auth.py      # Auth service (Argon2id, JWT, sessions)
│   ├── chat.py      # Chat orchestration
│   └── evaluations.py # Eval runner coordination
├── models/          # SQLAlchemy ORM models
│   ├── entities.py  # Users, conversations, orders, tickets
│   ├── auth.py      # RefreshSession, AuthAuditEvent
│   ├── knowledge.py # Documents, chunks, embeddings
│   ├── voice.py     # VoiceMessage, SpeechSynthesis
│   ├── channels.py  # Channel connections, events, handoff
│   └── evaluations.py # Datasets, runs, alerts, audit log
├── agents/          # Intent detection, language detection, response
├── workflows/       # Tool orchestration, confirmation flow
├── providers/       # LLM/STT/TTS provider abstraction (mock default)
├── security/        # Confirmation tokens, redaction
├── observability/   # Metrics, tracing, structured logging
├── core/            # Config, errors, middleware, Redis
└── database/        # Session factory, Base class
```

### Authentication Flow

```
Register → hash(pepper + password) → store Argon2id hash → return profile

Login → verify hash → create JWT access (15 min) + refresh session (7 day)
      → set refresh in HttpOnly cookie → return access token

Refresh → validate old refresh → revoke old → create new pair → rotate cookie

Logout → revoke refresh session → clear cookie
```

### Key Design Decisions

1. **Mock-first providers**: All AI providers default to deterministic mocks for testing
2. **Service layer auth**: Role checks in services, not just API layer
3. **Ownership enforcement**: Users can only access their own resources
4. **Fail-closed Redis**: Security features require Redis availability
5. **Structured logging**: JSON format with secret redaction filters

## Frontend Architecture

Next.js 15 App Router with:
- Server components where possible
- Client components for interactive features (chat, voice, auth)
- Token stored in memory (not localStorage)
- Refresh via HttpOnly cookie
- Tailwind CSS for styling

## Database

PostgreSQL 16 with pgvector extension for embedding storage.
Migrations managed by Alembic (0001–0007).

## Observability

- Prometheus metrics at `/metrics`
- OpenTelemetry tracing boundaries (console/no-op by default)
- Structured JSON logs with secret redaction
- Alert rules for error rate, latency, provider failures
