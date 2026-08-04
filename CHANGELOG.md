# Changelog

All notable changes to VaaniDesk are documented here.

## [1.0.0] — 2026-08-04

### Phase 7 — Production Auth, Security & Deployment

#### Added
- Argon2id password hashing with server-side pepper
- JWT access tokens (short-lived, Bearer auth) stored in frontend memory only
- Refresh token rotation with family-based reuse detection
- HttpOnly cookie refresh flow (Secure in production, SameSite documented)
- Registration, login, logout, logout-all endpoints
- Password change with session invalidation
- Session listing and individual revocation
- Brute-force protection with configurable lockout
- Role system: customer, support_agent, administrator
- Service-layer role and ownership enforcement
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, HSTS
- CSRF protection for cookie-authenticated routes (Origin validation)
- Request body size limits
- Config validation rejecting placeholder secrets in production
- Production Dockerfile (multi-stage, non-root, minimal runtime)
- docker-compose.prod.yml with Caddy reverse proxy, backend, frontend, worker, postgres, redis
- Caddyfile example with HTTPS, headers, upload limits
- GitHub Actions CI: backend (ruff, mypy, pytest), frontend (lint, build), security scan, Docker integration
- Backup script (pg_dump wrapper)
- Restore script (pg_restore wrapper with verification)
- Retention cleanup script (expired sessions, old audio, confirmation tokens)
- Frontend login page with register/sign-in toggle
- Frontend account page with profile, password change, session management
- Migration 0007: users auth columns + refresh_sessions + auth_audit_events tables
- Phase 7 security tests (password hashing, JWT, config validation, lockout, headers, auth flow)
- Documentation: SECURITY, ARCHITECTURE, API, DEPLOYMENT, BACKUP_RESTORE, DEMO, CONTRIBUTING, LICENSE

#### Changed
- All API endpoints now use unified auth (Bearer + demo header fallback)
- CORS restricted to explicit methods and headers
- TrustedHost middleware enabled
- Production docs/redoc hidden when DEBUG=false
- App version bumped to 1.0.0

## [0.6.0] — 2026-08-04

### Phase 6 — Evaluations & Observability
- 113-case multilingual eval dataset
- Deterministic eval runner with comparison/regression
- OpenTelemetry tracing, Prometheus metrics
- Structured logging with secret redaction
- Alert rules and audit log
- Admin pages: evaluations, observability, audit
- 172 tests passed

## [0.5.0] — 2026-08-04

### Phase 5 — Omnichannel Communication
- Email and WhatsApp channel adapters (dev simulators)
- Identity linking, external confirmation
- Transactional outbox, human handoff queue
- 127 tests passed

## [0.4.0] — 2026-08-04

### Phase 4 — Secure Multilingual Voice
- Audio upload, mock STT/TTS
- Transcript confirmation flow
- 86 tests passed

## [0.3.0] — 2026-08-04

### Phase 3 — Knowledge / RAG
- Document ingestion, hybrid retrieval
- Citations, no-answer detection

## [0.2.0] — 2026-08-04

### Phase 2 — Agent and Tools
- Intent detection, tool execution
- Confirmation flow, idempotency

## [0.1.0] — 2026-08-04

### Phase 1 — Working Foundation
- FastAPI backend, Next.js frontend
- PostgreSQL + Redis infrastructure
- Demo authentication
