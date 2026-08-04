# VaaniDesk — Task Tracker

Last updated: 2026-08-04 (Phase 7 complete; v1.0.0 released)

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` blocked · `[!]` risk

**Default branch:** `main`
**Tags:** `phase-1-complete` through `phase-7-complete`, `v1.0.0`
**Phase 4:** complete (`0e05e4c`, tag `phase-4-complete`) — 86 tests passed, 0 skipped
**Phase 5:** complete (`fc8ec61`, tag `phase-5-complete`) — 127 tests passed, 0 skipped
**Phase 6:** complete (`11d8c3a`, tag `phase-6-complete`) — 172 tests passed, 0 skipped; 113 eval cases
**Phase 7:** complete (tag `phase-7-complete`) — 197 tests passed, 0 failed; all gates green
**v1.0.0:** released (tag `v1.0.0`)

---

## Phase 0 — Environment and planning

- [x] Completed and approved

---

## Phase 1 — Working foundation

- [x] Completed, committed, tagged `phase-1-complete`

---

## Phase 2 — Agent and tools

- [x] Completed, committed, tagged `phase-2-complete`

---

## Phase 3 — Knowledge / RAG

- [x] Completed, committed, tagged `phase-3-complete`

---

## Phase 4 — Secure multilingual voice

- [x] Models + Alembic `0004_phase4` (VoiceMessage, SpeechSynthesis, VoiceTrace)
- [x] AudioStorage local FS + validation + rate limits
- [x] DeterministicMockSTT / DeterministicMockTTS
- [x] Transcript review/confirm/edit/submit through orchestrator
- [x] Voice API + ChatPanel voice UI + fixtures
- [x] docker-compose.test.yml + multi-stage Dockerfile
- [x] Quality gates: 86 passed, 0 skipped; ruff/mypy/frontend/Docker green
- [x] Commit `0e05e4c`, tag `phase-4-complete`

---

## Phase 5 — Omnichannel communication

- [x] Channel adapter boundary + models + migration `0005_phase5`
- [x] Email + WhatsApp-compatible adapters (dev simulators)
- [x] Identity linking + external sensitive confirmation
- [x] Outbox / delivery retries / human handoff
- [x] Operator channel UI (`/channels`)
- [x] Tests (41) + quality gates: 127 passed, 0 skipped

---

## Phase 6 — Evaluations / observability

- [x] Models + migration `0006_phase6_evals` (EvaluationDataset/Case/Run/Result, AlertRule/Event, AuditLogEntry)
- [x] Evaluation dataset ≥100 cases (113 cases, 21 categories, 5 languages, ~30 security-critical)
- [x] Deterministic eval runner with mock provider, JSON/MD export, comparison, regression thresholds
- [x] CI-friendly CLI: `python -m scripts.run_evaluations`
- [x] OpenTelemetry boundaries (console/no-op exporter by default)
- [x] Prometheus-compatible `/metrics` endpoint, no high-cardinality labels
- [x] Structured logging with redaction filters + tests proving secrets don't enter logs
- [x] Admin pages: `/admin/evaluations`, `/admin/observability`, `/admin/audit` (real APIs)
- [x] Alert rules (8 defaults): error-rate, latency, provider failure, unauthorized, confirmation replay, channel backlog, eval security regression, DB readiness
- [x] Load test script: `python -m scripts.load_test`
- [x] Tests: dataset validation, deterministic run, metrics, security, redaction, regression
- [x] Config + .env.example: OTEL_*, METRICS_*, EVAL_*, ALERT_* settings
- [x] Docs: BUILD_LOG, TASKS, README, EVALUATIONS.md

---

## Phase 7 — Production auth, security, deployment

- [x] Argon2id password hashing + server-side pepper
- [x] JWT access tokens (Bearer, frontend memory) + refresh-token family with rotation + reuse detection
- [x] Registration / login / logout / logout-all / password change
- [x] Refresh in HttpOnly cookie; Secure in production; SameSite documented
- [x] Session listing + revocation
- [x] Brute-force protection + login lockout
- [x] Roles: customer, support_agent, administrator (service-layer enforcement)
- [x] Auth audit events (safe, no PII beyond user ID)
- [x] CSRF for cookie-authenticated routes (Origin validation)
- [x] Strict CORS, trusted-host middleware
- [x] Security headers (CSP, X-Frame, MIME sniff, referrer, HSTS)
- [x] Config validation: reject placeholder secrets, insecure cookies, debug in production
- [x] Request-size limits
- [x] Migration 0007: users auth columns + refresh_sessions + auth_audit_events
- [x] Production containers: multi-stage, non-root, minimal runtime, health checks
- [x] docker-compose.prod.yml with backend/frontend/worker/postgres/redis/caddy
- [x] Caddy reverse proxy config (HTTPS, headers, upload limits)
- [x] GitHub Actions CI (backend lint/mypy/pytest + frontend lint/build + security scan + Docker integration)
- [x] Backup script (pg_dump)
- [x] Restore script (pg_restore + verification)
- [x] Retention cleanup (sessions, audio, confirmations)
- [x] Frontend: login page, account page, session management
- [x] Phase 7 security tests
- [x] Documentation: SECURITY, ARCHITECTURE, API, DEPLOYMENT, BACKUP_RESTORE, DEMO, CONTRIBUTING, LICENSE, CHANGELOG

---

## Open blockers

| ID  | Blocker                                                                | Needed for | Owner |
| --- | ---------------------------------------------------------------------- | ---------- | ----- |
| B6  | `uv run mypy` shim blocked by App Control; use `uv run python -m mypy` | Documented | —     |

---

## Notes

- Confirmation Redis key = `vd:confirm:` + SHA-256(raw token); payload omits raw token.
- RAG embeddings are deterministic lexical mocks — not production semantic embeddings.
- Phase 4 voice STT/TTS are deterministic mocks — not real speech providers.
- Phase 5 email/WhatsApp use labeled development simulators; no real external delivery in CI.
- External channel sensitive writes require authenticated web confirmation links.
- Phase 3 expected prompt hash `cf175b7` mismatched actual tagged commit `a9a7f33` — proceeded from actual tag.

