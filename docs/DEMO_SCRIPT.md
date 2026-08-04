# VaaniDesk v1.0.0 — Portfolio Demo Script (≈2–4 minutes)

Reproducible from a clean install with **mock providers** (no paid APIs). Prefer Docker Compose so frontend, backend, Postgres, and Redis stay aligned.

**Prep (once):**

```powershell
docker compose up --build -d
docker compose exec backend uv run alembic upgrade head
docker compose exec backend uv run python -m scripts.seed
docker compose exec backend uv run python -m scripts.seed_knowledge
```

Open http://localhost:3000 — stay on **demo user `demo-anya`** unless noted.

---

## 1. Introduction (≈20s)

- Land on the home page: **VaaniDesk — multilingual AI support across chat, voice and images**.
- One sentence: *production-shaped support agent with controlled tools, hybrid RAG, confirmations, evals, and security gates — running on deterministic mocks.*
- Click **Open chat demo**.

## 2. Hinglish customer message (≈25s)

In chat, send:

```text
mera order VD-10001 kahan hai
```

Call out language / script detection and intent routing in the workflow panel.

## 3. Language and intent handling (≈20s)

Point at the workflow card: detected language, intent, selected tool, tool status. Emphasize this is an **explicit workflow**, not free-form tool calling.

## 4. Controlled tool execution (≈20s)

Show the assistant reply for order status (seeded order `VD-10001` owned by Anya). Mention ownership AuthZ: another demo user cannot operate on Anya’s orders (covered by backend security tests / evals).

## 5. Policy question — hybrid RAG + citations (≈30s)

Send:

```text
what is your return policy for unused items?
```

Show **Citations** (document title, version, section, score). Note embeddings are a **deterministic lexical baseline**, not production semantic embeddings.

Optional Hindi follow-up:

```text
वापसी नीति क्या है?
```

## 6. Sensitive action confirmation (≈30s)

Send:

```text
please cancel my order VD-10001
```

Show **Confirmation required** with Approve / Deny. Click **Deny** (safe for live demos) and show the cleared pending state. Mention confirmation tokens, TTL, replay rejection, and idempotency (verified in tests — do not claim live cancel of production data).

## 7. Voice pipeline (≈30s)

On the same chat page, under **Mock STT/TTS**:

1. Upload a short WAV (or use Record if the browser allows).
2. Show transcript review → **Confirm transcript** → **Submit to workflow**.
3. Optionally play **mock TTS** on an assistant message.

State clearly: STT/TTS are deterministic mocks, not production speech quality.

*(Image note: channel attachment validation and damaged-product policy RAG exist; a dedicated vision model pipeline is not in v1.0.0 — skip fake “image analysis” demos.)*

## 8. Evaluation results (≈25s)

Open `/admin/evaluations` (admin/demo path as seeded). Trigger or open a recent run:

- **113 / 113** deterministic cases (mock provider)
- **40** security-critical cases, **0** security failures

Say: *this measures workflow and security regressions under mocks, not real LLM accuracy.*

## 9. Observability and security evidence (≈25s)

- `/admin/observability` — metrics / health-oriented view
- `/metrics` on the API — Prometheus scrape surface
- `/account` after register/login — sessions, Sign out (JWT path)
- One line on Argon2id + refresh rotation + CSRF/origin validation (point to `docs/SECURITY.md` if asked)

## 10. Architecture close (≈20s)

Return to README Mermaid (or `docs/ARCHITECTURE.md`):

**User / Channel → FastAPI → Controlled workflow → Tools / RAG → PostgreSQL + Redis → Mock providers → Traces / Evaluations.**

End on: *mock-first, fail-closed Redis for security paths, citations and confirmations are product requirements — not afterthoughts.*

---

## Do not claim in this demo

- Live OpenAI / Anthropic / cloud STT-TTS quality
- Production WhatsApp Cloud API or SMTP delivery
- Public multi-tenant SaaS deployment
- Implemented MCP `/mcp` server (planned / documented only)
- “100% accurate AI”
