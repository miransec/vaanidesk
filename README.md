# VaaniDesk

**Multilingual AI support across chat, voice and images**

VaaniDesk is a production-shaped AI customer-support platform for a fictional e-commerce company (portfolio project for **Puch AI**).

> **Status:** Phase 5 (omnichannel) in progress. Phase 4 complete (86 tests). Tagged baselines: `phase-1-complete` through `phase-4-complete`.

**Default Git branch:** `main`

---

## What works now (Phases 1–5)

- FastAPI `/health`, `/ready`, `/api/v1` chat + confirm + **knowledge** + **voice** + **channels** APIs
- Explicit workflow: language → intent → **tools or RAG** → AuthZ → confirmation → traces
- Tools: order status/details, address update, cancel eligibility/cancel, tickets, human queue
- Knowledge: Markdown/text/JSON ingest, versions, deterministic mock embeddings, FTS + pgvector, hybrid RRF, optional mock rerank
- Citations, configurable no-answer threshold, advisory injection scanning
- In-SQL document access control (public / authenticated / restricted allowlist)
- Knowledge seed path via `KNOWLEDGE_SEED_DIR` (Compose: `/sample_data/policies`; host fallback to repo `sample_data/policies`)
- **Voice** (Phase 4): upload → mock STT → transcript confirm → submit to orchestrator; mock TTS for responses
- Voice features: `VOICE_ENABLED` toggle, local `AudioStorage`, per-user rate limiting, transcript confirmation for sensitive intents
- **Channels** (Phase 5): omnichannel adapters (email dev inbox, WhatsApp simulator, web passthrough), HMAC-verified webhooks, inbound pipeline with dedup, identity linking, external confirmation for sensitive actions, transactional outbox, human handoff queue
- Next.js `/chat`, `/knowledge`, `/channels` operator pages
- Compose: postgres (pgvector), redis, backend, frontend
- `docker-compose.test.yml` for isolated test runs

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

## Docs

- [`PLAN.md`](./PLAN.md) · [`TASKS.md`](./TASKS.md)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · [`docs/API.md`](./docs/API.md)
- [`docs/SECURITY.md`](./docs/SECURITY.md) · [`docs/ADR.md`](./docs/ADR.md)

## License

MIT — see [`LICENSE`](./LICENSE).
