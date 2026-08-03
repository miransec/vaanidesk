# VaaniDesk

**Multilingual AI support across chat, voice and images**

VaaniDesk is a production-shaped AI customer-support platform for a fictional e-commerce company (portfolio project for **Puch AI**).

> **Status:** Phase 2 complete — controlled multilingual agent workflow + allow-listed business tools. Tagged baseline: `phase-1-complete`. Phase 3+ (RAG, voice, MCP, …) not started.

**Default Git branch:** `main`

---

## What works now (Phase 1 + 2)

- FastAPI `/health`, `/ready`, `/api/v1` chat + `POST /api/v1/actions/confirm`
- Explicit workflow: language → intent → tools → AuthZ → confirmation → traces
- Tools: order status/details, address update, cancel eligibility/cancel, tickets, human queue
- Public refs `VD-*` / `TKT-*`; ownership enforced in tools
- Redis confirmation tokens (fail closed) + Postgres idempotency records
- Next.js `/chat` with confirmation approve/deny + workflow metadata
- Compose: postgres (pgvector), redis, backend, frontend
- Tests: pytest 27 passed; ruff; mypy; frontend lint/build

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
```

Demo auth header: `X-Demo-User-Key: demo-anya` (not production).

Try: `where is my order VD-10001` · `mera order VD-10001 kidhar hai` · `please cancel my order VD-10001`

---

## Docs

- [`PLAN.md`](./PLAN.md) · [`TASKS.md`](./TASKS.md)
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) · [`docs/API.md`](./docs/API.md)
- [`docs/SECURITY.md`](./docs/SECURITY.md) · [`docs/ADR.md`](./docs/ADR.md)

## License

MIT — see [`LICENSE`](./LICENSE).
