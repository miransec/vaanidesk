# VaaniDesk Build Log

Do not store secrets in this file.

## Environment (Phase 4 start)

| Item | Value |
|------|-------|
| Start commit | `a9a7f3379f5b07829b74e5bfedb1871d7b1706d0` |
| Expected prompt hash | `cf175b7` (actual tagged Phase 3 is `a9a7f33`) |
| Tag | `phase-3-complete` |
| Branch | `main` |
| Working tree | clean at Phase 4 start |
| Python | 3.12.13 (uv) |
| Node | v24.18.1 |
| Docker | 29.6.2 |

## Phase 4 â€” Secure multilingual voice

### Start
- Began from `phase-3-complete` / `a9a7f33`

### Migrations
- `0004_phase4_voice` (revision `0004_phase4`)

### Models added
- `VoiceMessage` â€” upload metadata, transcript, confirmation state
- `SpeechSynthesis` â€” TTS output records
- `VoiceTrace` â€” per-request audit/observability

### Components delivered
- `backend/app/voice/` â€” STT, TTS, validation, rate limiting, storage modules
- `backend/app/api/v1/voice.py` â€” full voice endpoint router
- `backend/app/services/voice.py` â€” service layer
- `backend/app/schemas/voice.py` â€” request/response models
- `docker-compose.test.yml` â€” isolated test Compose stack
- `backend/Dockerfile` â€” multi-stage runtime + test target
- `frontend/src/components/ChatPanel.tsx` â€” voice recording UI
- `sample_data/audio/` â€” fixture WAV files for tests

### Notes
- Voice is a transport into the existing controlled orchestrator
- Default STT/TTS providers are deterministic mocks (`DeterministicMockSTT`, `DeterministicMockTTS`)
- Audio stored on local filesystem via `AudioStorage` protocol (no S3 required)
- Transcript confirmation required before submitting sensitive intents
- Rate limiting per user (uploads/min, bytes/hour, STT/TTS reqs/min, concurrent jobs)

### Quality gates (Phase 4 completion)

| Check | Result |
|-------|--------|
| `uv run pytest -rs` | **86 passed, 0 skipped** |
| `ruff check .` | Pass |
| `ruff format --check .` | Pass |
| `python -m mypy app` | Pass |
| `npm run lint` | Pass |
| `npm run build` | Pass |
| Docker rebuild + health | Pass (backend healthy) |
| Migration cycle (down 0003 â†’ up 0004) | Pass |
| Knowledge seed Ã—2 | `already_present` 17 docs / 241 chunks |

### Known limitations
- STT/TTS are deterministic mocks only â€” no real speech quality claims
- Audio storage is local filesystem; no S3 integration required for demo
- No production voice provider credentials needed

### Commit / tag
- Commit: `0e05e4c` â€” `feat: complete VaaniDesk phase 4 secure multilingual voice`
- Tag: `phase-4-complete`

---

---

## Phase 5 â€” Omnichannel Communication

### Start state
| Item | Value |
|------|-------|
| Start commit | `0e05e4c` |
| Tag | `phase-4-complete` |
| Branch | `main` |
| Alembic head | `0004_phase4` |

### Implementation summary
- Created `app/models/channels.py` with 10 models covering channel connections, identities, inbound/outbound messaging, delivery attempts, attachments, identity linking, external confirmations, and human handoff
- Migration `0005_phase5_channels` adds all tables with proper enums and constraints
- Channel adapter boundary in `app/channels/` with protocol/ABC, HMAC signatures (constant-time compare + replay protection), inbound pipeline, transactional outbox, renderers, attachment validation, identity linking, human handoff management
- Email adapter with dev inbox (deterministic, no real SMTP) + HTML sanitize + subject threading
- WhatsApp adapter with Meta-style webhook schema + verification challenge + simulator
- Web adapter (thin passthrough noting existing chat API)
- API routers for webhooks, simulator, connections, identity linking, external confirmation, outbound retry, handoff queue
- Services layer with full business logic and authorization
- Frontend `/channels` operator page with connections, simulator, events, deliveries, handoff queue
- Comprehensive test suite covering HMAC, dedup, adapters, attachments, linking, external confirm, renderers, handoff, API integration

### Files created/modified
- `backend/app/models/channels.py` (new)
- `backend/alembic/versions/0005_phase5_channels.py` (new)
- `backend/app/channels/` package (new)
- `backend/app/schemas/channels.py` (new)
- `backend/app/services/channels.py` (new)
- `backend/app/api/v1/channels.py` (new)
- `backend/tests/test_phase5_channels.py` (new â€” 41 tests)
- `frontend/src/app/channels/page.tsx` (new)
- Config, router, models/__init__.py, alembic/env.py, .env.example updated

### Quality gates (Phase 5 completion)

| Check | Result |
|-------|--------|
| `uv run pytest -rs` | **127 passed, 0 skipped** (86 prior + 41 Phase 5) |
| `ruff check .` | Pass |
| `ruff format --check .` | Pass |
| `python -m mypy app` | Pass |
| `npm run lint` | Pass |
| `npm run build` | Pass |

### Known limitations
- Email and WhatsApp use development simulators â€” no real SMTP/Meta delivery
- External sensitive actions require authenticated web confirmation links
- Unlinked channel identities cannot access account-scoped order data

### Commit / tag
- Commit: `fc8ec61` — feat: complete VaaniDesk phase 5 omnichannel support
- Tag: `phase-5-complete`

---

## Phase 6 — Evaluations, Observability, and Operations

### Start state
| Item | Value |
|------|-------|
| Start commit | `fc8ec61` |
| Tag | `phase-5-complete` |
| Branch | `main` |
| Alembic head | `0005_phase5` |

### Implementation summary
- Created `app/models/evaluations.py` with 7 models: EvaluationDataset, EvaluationCase, EvaluationRun, EvaluationResult, AlertRule, AlertEvent, AuditLogEntry
- Migration `0006_phase6_evals` adds all tables with proper enums, indexes, and constraints
- Evaluation dataset with 113 multilingual cases across 21 categories, 5 languages, ~30 security-critical cases
- Deterministic mock evaluation runner with JSON/Markdown export, comparison/regression detection
- CI-friendly CLI: `python -m scripts.run_evaluations`
- OpenTelemetry boundaries (console/no-op exporter by default, configurable)
- Prometheus-compatible `/metrics` endpoint with no high-cardinality labels
- Structured logging with redaction filters (tested: API keys, Bearer tokens, body content blocked)
- Trace spans with automatic secret redaction (no raw tokens/audio/bodies)
- In-memory metrics collector: counters, latency histograms (avg/p95/p99)
- Alert rules system: 8 default rules (error rate, latency, provider failure, unauthorized, confirmation replay, channel backlog, eval security regression, DB readiness)
- Audit log for system events with safe metadata
- Admin frontend pages: `/admin/evaluations`, `/admin/observability`, `/admin/audit` (real APIs, no static charts)
- Load test script: `python -m scripts.load_test`
- Operational snapshot API: DB aggregates + in-memory counters

### Files created
- `backend/app/models/evaluations.py`
- `backend/alembic/versions/0006_phase6_evals.py`
- `backend/app/evals/` (dataset, runner)
- `backend/app/observability/` (tracing, metrics, logging_filters)
- `backend/app/schemas/evaluations.py`
- `backend/app/services/evaluations.py`
- `backend/app/api/v1/evaluations.py`
- `backend/scripts/run_evaluations.py`
- `backend/scripts/load_test.py`
- `backend/tests/test_phase6_evals.py`
- `frontend/src/app/admin/evaluations/page.tsx`
- `frontend/src/app/admin/observability/page.tsx`
- `frontend/src/app/admin/audit/page.tsx`
- `docs/EVALUATIONS.md`

### Files modified
- `backend/app/models/__init__.py` — Phase 6 model exports
- `backend/app/api/v1/router.py` — evaluations router
- `backend/alembic/env.py` — Phase 6 model imports
- `backend/app/main.py` — metrics endpoint, redaction filter, tracing init
- `backend/app/core/config.py` — Phase 6 config vars
- `frontend/src/app/layout.tsx` — admin nav links
- `frontend/src/lib/api.ts` — Phase 6 types
- `.env.example` — OTEL_*, METRICS_*, EVAL_*, ALERT_* settings

### Quality gates (Phase 6 completion)

| Check | Result |
|-------|--------|
| `uv run pytest -rs` | **172 passed, 0 skipped** (127 prior + 45 Phase 6) |
| `ruff check .` | Pass |
| `ruff format --check .` | Pass |
| `python -m mypy app` | Pass (95 source files) |
| Eval dataset case count | 113 |
| Security-critical cases | ~40 |
| Languages covered | en, hi, mr, hinglish, unknown |
| Categories covered | 21 |

### Known limitations
- All evaluations use mock provider — scores reflect deterministic behavior, not real LLM quality
- OpenTelemetry uses console/no-op exporter by default (configure OTEL_EXPORTER_OTLP_ENDPOINT for production)
- Alert rules store/log in dev — no PagerDuty/Slack integration claimed
- Admin auth remains demo-key based (Phase 7 hardens auth)

### Commit / tag
- Commit: 11d8c3a — feat: complete VaaniDesk phase 6 evaluations and observability
- Tag: phase-6-complete

---

## Phase 7 — Production auth, security & deployment

### Start
- Base commit: `11d8c3a` (tag `phase-6-complete`)
- Existing tests: 172 passed, 0 skipped

### Implementation

#### Authentication
- Argon2id password hashing with server-side pepper (HMAC-SHA256)
- JWT access tokens (HS256, 15-min expiry, Bearer header)
- Refresh token rotation with SHA-256 hashing and family-based reuse detection
- HttpOnly cookie for refresh token (Secure in production, SameSite=lax)
- Registration, login, logout, logout-all, password change
- Session listing and revocation
- Brute-force lockout (5 attempts → 15 min lock, configurable)
- Auth audit events

#### Roles
- UserRole enum: customer, support_agent, administrator
- Service-layer enforcement via `require_role()` dependency
- All API endpoints migrated from `get_demo_user` to `get_current_user` (Bearer + demo fallback)

#### Security hardening
- SecurityHeadersMiddleware: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS
- CsrfMiddleware: Origin validation for cookie-authenticated state-changing requests
- RequestSizeLimitMiddleware: configurable max body size
- TrustedHostMiddleware enabled
- Strict CORS with explicit methods/headers (no wildcard in production)
- Config validation: rejects placeholder secrets, insecure cookies, debug in production
- Docs/Redoc hidden when DEBUG=false

#### Database
- Migration 0007: `password_hash`, `role`, `is_disabled`, `failed_login_attempts`, `locked_until` on users; `refresh_sessions` and `auth_audit_events` tables
- `demo_key` column changed to nullable (production users may not have demo keys)

#### Containers & deployment
- docker-compose.prod.yml: backend, frontend, worker, postgres, redis, caddy
- Caddy reverse proxy with HTTPS, security headers, upload limits
- Worker container for retention cleanup
- Non-root containers, read-only FS, health checks

#### CI/CD
- `.github/workflows/ci.yml`: backend (ruff, format, mypy, pytest), frontend (lint, build), security (gitleaks), integration (Docker test stack)

#### Scripts
- `scripts/backup.py`: pg_dump wrapper with timestamp naming
- `scripts/restore.py`: pg_restore with verification
- `scripts/retention_cleanup.py`: expire sessions, old audio, confirmation tokens

#### Frontend
- Login page (`/login`): register/sign-in toggle, demo mode link
- Account page (`/account`): profile, password change, session management
- Auth library (`lib/auth.ts`): token in memory, refresh flow, no localStorage

#### Documentation
- SECURITY.md, ARCHITECTURE.md, API.md, DEPLOYMENT.md, BACKUP_RESTORE.md, DEMO.md
- CONTRIBUTING.md, LICENSE (MIT), CHANGELOG.md
- Updated README, TASKS, BUILD_LOG

### Quality gates (Phase 7 completion)

| Check | Result |
|-------|--------|
| `uv run pytest -rs` | **197 passed, 0 failed** (172 prior + 25 Phase 7) |
| `ruff check .` | Pass (130 files) |
| `ruff format --check .` | Pass (130 files already formatted) |
| `python -m mypy app` | Pass (pre-existing untyped decorator warnings only) |
| Frontend `npm run lint` | Pass (0 errors) |
| Frontend `npm run build` | Pass (13 static pages) |

### New files
- `backend/app/models/auth.py`
- `backend/app/services/auth.py`
- `backend/app/schemas/auth.py`
- `backend/app/api/v1/auth.py`
- `backend/app/core/security.py`
- `backend/alembic/versions/0007_phase7_auth.py`
- `backend/scripts/backup.py`
- `backend/scripts/restore.py`
- `backend/scripts/retention_cleanup.py`
- `backend/tests/test_phase7_auth.py`
- `frontend/src/lib/auth.ts`
- `frontend/src/app/login/page.tsx`
- `frontend/src/app/account/page.tsx`
- `docker-compose.prod.yml`
- `deploy/Caddyfile`
- `.github/workflows/ci.yml`
- `docs/SECURITY.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/DEPLOYMENT.md`
- `docs/BACKUP_RESTORE.md`, `docs/DEMO.md`
- `CONTRIBUTING.md`, `LICENSE`, `CHANGELOG.md`

### Known limitations
- All providers remain deterministic mocks — production would need real LLM/STT/TTS integration
- Rate limiting is request-size-based; per-IP sliding window requires Redis middleware (documented, not wired)
- Encrypted credential storage uses established Argon2id + pepper; DB-level column encryption deferred

---

_Results appended at each phase checkpoint._

