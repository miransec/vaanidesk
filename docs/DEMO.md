# VaaniDesk — One-Command Demo

## Quick Start

```bash
# Clone and start
git clone <repo-url> && cd vaanidesk
cp .env.example .env

# Start everything
docker compose up --build -d

# Wait for health
until curl -sf http://localhost:8000/health; do sleep 2; done

# Run migrations and seed
docker compose exec backend uv run alembic upgrade head
docker compose exec backend uv run python -m scripts.seed
docker compose exec backend uv run python -m scripts.seed_knowledge

# Open
echo "Frontend: http://localhost:3000"
echo "Backend API: http://localhost:8000/docs"
echo "Health: http://localhost:8000/health"
echo "Metrics: http://localhost:8000/metrics"
```

## Demo Credentials

| User | Demo Key | Role | Email |
|------|----------|------|-------|
| Anya | `demo-anya` | customer | anya@demo.vaanidesk.test |
| Ravi | `demo-ravi` | customer | ravi@demo.vaanidesk.test |
| Priya | `demo-priya` | support_agent | priya@demo.vaanidesk.test |
| Admin | `demo-admin` | administrator | admin@demo.vaanidesk.test |

Demo users have password `DemoP@ss123!` when using production auth (registration also available).

## Features to Try

1. **Chat**: Send messages in English, Hindi, Marathi, or Hinglish
2. **Knowledge**: Browse policy documents, test retrieval and citations
3. **Voice**: Upload audio for transcription (mock STT) and mock TTS playback
4. **Channels**: Simulate email/WhatsApp events (simulators — not live Cloud API)
5. **Evaluations**: Run the 113-case mock suite; inspect security-critical results
6. **Auth**: Register, login, manage sessions, sign out
7. **Confirmations**: Cancel order flow with Approve / Deny UI

Portfolio narrative: [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md).

## Mock Badges

All AI providers run in deterministic mock mode:
- LLM: Workflow-heuristic responses (not a real LLM)
- STT/TTS: Deterministic mock transcription/synthesis
- Embeddings: Lexical n-gram hashing (not semantic)

No paid API keys required.

## Reset

```bash
docker compose down -v
docker compose up --build -d
# Re-run migrations + seed
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Port 5432 in use | Stop local PostgreSQL or change `POSTGRES_PORT` |
| Port 3000 in use | Stop other Node.js servers |
| Migrations fail | Ensure PG is healthy: `docker compose logs postgres` |
| Redis connection refused | Check Redis health: `docker compose logs redis` |
