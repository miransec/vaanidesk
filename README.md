# VaaniDesk

**Multilingual AI support across chat, voice and images**

VaaniDesk is a production-shaped AI customer-support platform for a fictional e-commerce company (portfolio project for **Puch AI**).

> **Status:** Phase 1 foundation implemented. Full Compose verification may be blocked until Docker Desktop is installed with Administrator privileges. Phase 2+ features are **not** implemented.

**Default Git branch:** `main`

---

## What works in Phase 1

- FastAPI backend with `/health`, `/ready`, and `/api/v1` chat APIs
- Next.js frontend (`/` and `/chat`)
- SQLAlchemy models: User, Conversation, Message, Product, Order, OrderItem
- Alembic migration enabling pgvector extension when available
- Idempotent sample-data seed (4 demo users, 25 products, 50 orders)
- Deterministic **mock** LLM provider (English / Hindi / Hinglish / Marathi demos)
- Demo authentication via headers (not production auth)
- Docker Compose definition + Dockerfiles
- Unit tests, Ruff, frontend lint/typecheck/build

---

## Prerequisites

| Tool | Version |
|------|---------|
| Git | branch `main` |
| Python | **3.12** via `uv` (see `.python-version`) — do not use host 3.14 |
| Node.js | **24** LTS (see `.nvmrc`) |
| npm | ships with Node |
| Docker Desktop | required for Postgres+pgvector + Compose stack |
| uv | package manager for backend |

### Local Python setup

```powershell
uv python install 3.12
cd backend
uv sync --extra dev
```

Confirm: `uv python find 3.12` and `uv run python -c "import sys; print(sys.version)"` shows 3.12.x.

### Frontend setup

```powershell
cd frontend
npm ci
copy .env.local.example .env.local
npm run dev
```

### Docker Compose setup

```powershell
copy .env.example .env
docker compose up --build
```

Then migrate + seed (from host against published Postgres port, or exec into backend):

```powershell
cd backend
$env:DATABASE_URL="postgresql+asyncpg://vaanidesk:vaanidesk_dev_password@localhost:5432/vaanidesk"
uv run alembic upgrade head
uv run python -m scripts.seed
```

### Tests

```powershell
cd backend
uv run pytest tests/test_unit.py -v
uv run ruff check app tests scripts
uv run ruff format --check app tests scripts
# mypy: may be blocked by Windows Application Control on some machines
uv run mypy app

cd ../frontend
npm run lint
npm run typecheck
npm run build
```

Integration tests (`tests/test_integration.py`) require a live Postgres matching `DATABASE_URL` and seeded data.

---

## Demo users (Phase 1)

| demo_key | display name | stable UUID |
|----------|--------------|-------------|
| `demo-anya` | Anya Mehta | `11111111-1111-1111-1111-111111111111` |
| `demo-rahul` | Rahul Nair | `22222222-2222-2222-2222-222222222222` |
| `demo-priya` | Priya Deshmukh | `33333333-3333-3333-3333-333333333333` |
| `demo-arjun` | Arjun Kapoor | `44444444-4444-4444-4444-444444444444` |

Send either header:

- `X-Demo-User-Key: demo-anya`
- `X-Demo-User-Id: 11111111-1111-1111-1111-111111111111`

**This is demo authentication only — not production-ready.**

---

## Mock provider

`LLM_PROVIDER=mock` (default). Pattern-based deterministic replies for greetings and simple order-status phrasing. Responses include metadata `is_mock: true` and explicitly state they are not a production model.

Example phrases: `hello`, `namaste`, `mera order kahan hai`, `मेरा ऑर्डर कहाँ है`, `माझी ऑर्डर कुठे आहे`.

---

## API (Phase 1)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | liveness |
| GET | `/ready` | Postgres required; Redis reported |
| GET | `/api/v1/demo-users` | list seeded demo users |
| POST | `/api/v1/chat/messages` | create message + mock reply |
| GET | `/api/v1/conversations` | list current demo user's conversations |
| GET | `/api/v1/conversations/{id}` | detail; **403** for other users |

OpenAPI: `http://localhost:8000/docs`

---

## Current limitations

- No business tool calling, RAG, voice, images, WhatsApp, MCP, evals, or ops dashboard
- Demo header auth only
- Mock provider is not semantic AI
- Docker Desktop may require a manual Administrator install + restart on Windows
- `mypy` may be blocked by Windows Application Control (documented)

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [`PLAN.md`](./PLAN.md) | Phased plan |
| [`TASKS.md`](./TASKS.md) | Checklist |
| [`docs/ADR.md`](./docs/ADR.md) | Decisions |
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Architecture |
| [`docs/API.md`](./docs/API.md) | API notes |
| [`LICENSE`](./LICENSE) | MIT |

---

## License

[MIT](./LICENSE)
