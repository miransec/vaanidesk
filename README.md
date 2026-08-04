# VaaniDesk

**Multilingual AI support across chat, voice and images**

VaaniDesk is a production-shaped AI customer-support platform for a fictional e-commerce company (portfolio project for **Puch AI**).

> **Status:** v1.0.0 — Phase 7 (production auth, security, deployment) complete. All quality gates green. Tagged baselines: `phase-1-complete` through `phase-7-complete`, `v1.0.0`.

**Default Git branch:** `main`

---

## What works now (Phases 1–7)

- **Authentication** (Phase 7): Argon2id password hashing + server-side pepper, JWT access tokens (Bearer), refresh token rotation with reuse detection, HttpOnly cookie refresh, login/register/logout/logout-all, password change, session listing + revocation, brute-force lockout
- **Roles**: customer / support_agent / administrator with service-layer enforcement
- **Security hardening**: strict CORS, trusted-host, CSP/X-Frame/MIME-sniff/referrer headers, CSRF for cookie auth, request-size limits, config validation rejecting weak secrets in production
- **Production deployment**: multi-stage Docker, non-root containers, docker-compose.prod.yml with Caddy reverse proxy (HTTPS), read-only FS, health checks
- **CI/CD**: GitHub Actions for backend (lint, format, mypy, pytest, audit) + frontend (lint, build, audit) + security scan + Docker integration
- **Scripts**: backup (pg_dump), restore (pg_restore), retention cleanup (sessions, audio, confirmations)
- FastAPI `/health`, `/ready`, `/metrics`, `/api/v1` chat + confirm + **knowledge** + **voice** + **channels** + **evaluations** + **auth** APIs
- Explicit workflow: language → intent → **tools or RAG** → AuthZ → confirmation → traces
- Tools: order status/details, address update, cancel eligibility/cancel, tickets, human queue
- Knowledge: Markdown/text/JSON ingest, versions, deterministic mock embeddings, FTS + pgvector, hybrid RRF, optional mock rerank
- Citations, configurable no-answer threshold, advisory injection scanning
- **Voice** (Phase 4): upload → mock STT → transcript confirm → submit to orchestrator; mock TTS for responses
- **Channels** (Phase 5): omnichannel adapters (email dev inbox, WhatsApp simulator, web passthrough), HMAC-verified webhooks, identity linking, human handoff queue
- **Evaluations** (Phase 6): 113-case multilingual eval dataset, deterministic runner, comparison/regression detection
- **Observability** (Phase 6): OpenTelemetry tracing, Prometheus `/metrics`, structured logging with secret redaction, alert rules
- Next.js `/login`, `/account`, `/chat`, `/knowledge`, `/channels`, `/admin/*` pages
- Compose: postgres (pgvector), redis, backend, frontend, caddy (production)
- `docker-compose.test.yml` for isolated CI test runs

---

## Prerequisites

| Tool | Version |
|------|---------|
| Git | branch `main` |
| Python | **3.12** via `uv` |
| Node.js | **24** LTS |
| Docker Desktop | Compose stack |
| uv | backend package manager |

### Backend

```powershell
cd backend
uv sync --extra dev
uv run alembic upgrade head
uv run python -m scripts.seed
uv run python -m scripts.seed_knowledge
uv run uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm ci
npm run dev
```

### Compose

```powershell
docker compose up --build
# Inside the backend container (corpus mounted at /sample_data):
docker compose exec backend uv run python -m scripts.seed
docker compose exec backend uv run python -m scripts.seed_knowledge
```

### Test Compose

```powershell
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit
```

`KNOWLEDGE_SEED_DIR` defaults to `/sample_data/policies` in Compose (`./sample_data` → `/sample_data:ro`). On the host, leave it unset to use `<repository-root>/sample_data/policies`. The seed script fails clearly if `manifest.json` is missing.

Demo auth header: `X-Demo-User-Key: demo-anya` (not production).

Try:

- `where is my order VD-10001`
- `what is your return policy`
- `वापसी नीति क्या है?`
- `please cancel my order VD-10001`

---

## Phase 4 voice notes

- Voice is a **transport** into the existing controlled orchestrator — not a separate agent
- STT/TTS providers: `DeterministicMockSTT` / `DeterministicMockTTS` (no real speech quality claims)
- Audio storage: local filesystem (`AUDIO_STORAGE_DIR`); no S3 required for demo
- Toggle: `VOICE_ENABLED=true` in `.env`
- Transcript confirmation required before submitting sensitive intents
- Rate limits: uploads/min, bytes/hour, STT/TTS requests/min, max concurrent jobs (all configurable)

---

## Phase 3 knowledge notes

- Embeddings: **Deterministic lexical embedding baseline for local development and testing — not production semantic embeddings.**
- Hybrid fusion: Reciprocal Rank Fusion with `k=60`
- Confidence threshold: `RAG_MIN_RETRIEVAL_CONFIDENCE` (default `0.30`)
- Knowledge corpus: set `KNOWLEDGE_SEED_DIR` or rely on host fallback `<repo>/sample_data/policies`
- Restricted sample doc “Internal Override Notes” is allowlisted to `demo-anya` only (injection bait; cannot trigger tools)

---

## Phase 6 evaluation notes

- Evaluations run against **mock provider** by default — scores reflect deterministic mock behavior, not real LLM quality
- Dataset: 113 cases across 5 languages and 21 categories (~30 security-critical)
- Security-critical failures cause the entire run to **fail** (ownership leak, unauthorized write, confirmation bypass, fabricated citation)
- CLI: `cd backend && uv run python -m scripts.run_evaluations`
- Admin UI: `/admin/evaluations` for runs, `/admin/observability` for metrics, `/admin/audit` for audit log
- OpenTelemetry: console/no-op by default; set `OTEL_EXPORTER_OTLP_ENDPOINT` for production
- Alert rules store/log in dev — no PagerDuty/Slack claimed
- Load test: `cd backend && uv run python -m scripts.load_test`

---

## Docs

- [`PLAN.md`](./PLAN.md) · [`TASKS.md`](./TASKS.md)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · [`docs/API.md`](./docs/API.md)
- [`docs/SECURITY.md`](./docs/SECURITY.md) · [`docs/ADR.md`](./docs/ADR.md)
- [`docs/EVALUATIONS.md`](./docs/EVALUATIONS.md)

## License

MIT — see [`LICENSE`](./LICENSE).
