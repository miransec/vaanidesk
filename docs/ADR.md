# Architectural Decision Records (ADRs)

Finalized decisions for VaaniDesk. Narrative context remains in [`PLAN.md`](../PLAN.md) and [`ARCHITECTURE.md`](./ARCHITECTURE.md). New decisions get a new ADR entry; do not silently rewrite history without a supersession note.

---

## ADR-001 — Monorepo layout

**Status:** Accepted
**Decision:** Single repository with `backend/`, `frontend/`, `mcp_server/`, `evals/`, `sample_data/`, `docs/`.
**Why:** One portfolio artifact; shared sample data and docs; coordinated versioning for demos.

---

## ADR-002 — Provider interfaces with mock default

**Status:** Accepted
**Decision:** Abstract chat, structured intent, embeddings, STT, TTS, and vision behind interfaces. `LLM_PROVIDER=mock|openai|anthropic` (and sibling provider env vars).
**Why:** Tests and demos run without paid keys; production providers stay swappable.

---

## ADR-003 — Controlled agent workflow

**Status:** Accepted
**Decision:** Explicit multi-step orchestrator; no unbounded autonomous tool loop.
**Why:** Auditable traces, safer AuthZ boundaries, clearer evaluation.

---

## ADR-004 — Allow-listed tools only

**Status:** Accepted
**Decision:** Server-side tool registry with typed schemas; models never call arbitrary functions or touch the DB directly.
**Why:** Prevent tool-name injection and over-broad model permissions.

---

## ADR-005 — Hybrid RAG

**Status:** Accepted
**Decision:** pgvector similarity + PostgreSQL full-text/keyword search, fusion, optional rerank, citations, no-answer path.
**Why:** Production-shaped retrieval with comparable strategies in evals.

---

## ADR-006 — Separate MCP service (SDK v2 + Streamable HTTP)

**Status:** Accepted
**Decision:** Deploy MCP as its own process. Use the **current MCP Python SDK v2** with **Streamable HTTP** transport, exposing `/mcp`. Keep a **Puch compatibility layer** for Puch-specific bearer authentication and mandatory application tools (`validate`, `resume`).
**Why:** Process isolation, HTTPS-friendly deploy, protocol-correct transport, and explicit Puch application requirements without coupling Puch auth quirks into core MCP SDK usage.

---

## ADR-007 — Confirmation + idempotency for sensitive tools

**Status:** Accepted
**Decision:** Cancel, address change, refund creation (and similar) require confirmation tokens. Persist **idempotency records** keyed by `(user_id, tool_name, idempotency_key)` so retries do not double-apply destructive effects.
**Why:** Safe UX under retries/webhooks; prevent duplicate cancellations and refunds.

---

## ADR-008 — Per-user data isolation

**Status:** Accepted
**Decision:** Every customer data access is scoped by authenticated `user_id` (and MCP `puch_user_id` mapping).
**Why:** Block IDOR and cross-user leakage.

---

## ADR-009 — Docker Compose locally; managed data plane in production docs

**Status:** Accepted
**Decision:** Local Postgres+pgvector and Redis via Compose; production docs assume managed PG/Redis.
**Why:** Reproducible demos; realistic deploy story.

---

## ADR-010 — Structured traces as source of truth

**Status:** Accepted
**Decision:** JSON logs plus persisted trace/tool records feed the dashboard and evals.
**Why:** One observability pipeline; no fabricated dashboard numbers.

---

## ADR-011 — Python 3.12 only for backend and MCP

**Status:** Accepted
**Decision:** `requires-python = ">=3.12,<3.13"` in backend and MCP `pyproject.toml`; root `.python-version` = `3.12`; commit `uv.lock` when projects exist. Host may have 3.14 — do not target it.
**Why:** Dependency compatibility and reproducible CI/Docker images.

---

## ADR-012 — Channel adapters with honest simulator

**Status:** Accepted
**Decision:** Web chat + WhatsApp Cloud adapter + labeled local simulator when credentials are absent.
**Why:** Fully demonstrable without faking a live WhatsApp integration.

---

## ADR-013 — API versioning

**Status:** Accepted
**Decision:** Version business APIs under `/api/v1/...`. Keep `/health`, `/ready`, and MCP `/mcp` **unversioned**.
**Why:** Stable ops/probe and MCP entrypoints; evolvable product API.

---

## ADR-014 — Default Git branch `main`

**Status:** Accepted
**Decision:** Use `main` as the default branch (rename from empty-repo `master` before first commit / Phase 1).
**Why:** Current GitHub/Git default; avoid `master` in new portfolio work.

---

## ADR-015 — Redis fail-closed vs degrade

**Status:** Accepted
**Decision:**

- **May degrade gracefully** when Redis is unavailable: optional response caches, non-security read-through caches, best-effort metrics buffers.
- **Must fail closed** when Redis is unavailable: confirmation tokens, webhook replay protection, sensitive-action authorization state, and security rate limits.

**Why:** Availability for non-critical paths must not weaken authorization or replay defenses.

---

## ADR-016 — Mock embeddings are lexical baselines, not semantics

**Status:** Accepted
**Decision:** Mock embedding provider uses **deterministic lexical hashing** over normalized word and/or character n-grams to produce fixed-dimension vectors for offline tests.
**Why:** Reproducible RAG plumbing tests without API keys. **Not** production semantic embeddings — real embedding providers are required for meaningful semantic retrieval quality.

---

## ADR-017 — Phased database model rollout

**Status:** Accepted
**Decision:** Phase 1 foundation models only: `User`, `Conversation`, `Message`, `Product`, `Order`, `OrderItem`. Later phases add `SupportTicket`, knowledge tables, traces/tools, feedback, and evaluation tables.
**Why:** Keep Phase 1 thin and shippable; avoid unused schema surface before workflows exist.

---

## ADR-018 — Node.js 24 LTS for frontend

**Status:** Accepted
**Decision:** Frontend targets Node.js **24** LTS; root `.nvmrc` contains `24`; commit the frontend package-manager lockfile.
**Why:** Align with current LTS for the portfolio timeline; reproducible installs.

---

## ADR-019 — Puch mandatory MCP application tools

**Status:** Accepted
**Decision:** MCP server exposes Puch application tools `validate` and `resume` in addition to support tools. `validate` returns `PUCH_PHONE_NUMBER`. `resume` returns Markdown from `RESUME_MARKDOWN_PATH`. Auth uses `PUCH_APPLICATION_KEY` via the Puch compatibility bearer layer. Never hardcode key, phone, or resume body.
**Why:** Meet Puch application MCP requirements while keeping secrets and resume content out of source.

---

## ADR-020 — Phase 2 controlled workflow (not an autonomous loop)

**Status:** Accepted
**Decision:** Phase 2 support handling is an explicit step orchestrator (`language → intent → clarify → allow-listed tool → AuthZ → risk → confirmation → execute → respond → escalate → traces`). No free-running agent loop. Heuristic language/intent detectors sit behind replaceable interfaces.
**Why:** Auditable, testable steps; deterministic mock demos; safer AuthZ and confirmation gates.

---

## ADR-021 — Public business identifiers

**Status:** Accepted
**Decision:** Customers see `VD-xxxxx` order refs and `TKT-xxxxx` ticket refs. Internal UUIDs are not required in chat. Lookups always combine authenticated user identity with the public ref.
**Why:** Prevent IDOR via guessed UUIDs; keep demos readable.

---

## ADR-022 — Confirmation + durable idempotency for high-risk tools

**Status:** Accepted
**Decision:** High-risk tools use Redis confirmation tokens (fail closed) **and** Postgres `IdempotencyRecord` rows for mutations. The client receives a raw URL-safe token once; Redis stores only `SHA-256(token)` as the key and never persists the raw token in the JSON payload. Tokens bind user, tool, and argument hash; single-use with TTL. Concurrent idempotency inserts use a savepoint and unique constraint so only one winner executes.
**Why:** Prevent accidental/duplicate destructive actions even under retries, races, or Redis outages after commit.

---

## ADR-023 — In-SQL knowledge access control

**Status:** Accepted
**Decision:** Document visibility (`public` / `authenticated` / `restricted`+allowlist) is enforced in the retrieval SQL join/filter before keyword or vector candidates are materialized in application memory.
**Why:** Unauthorized chunks must never reach fusion, reranking, model context, citations, or trace bodies.

---

## ADR-024 — Hybrid RRF + mock rerank

**Status:** Accepted
**Decision:** Hybrid retrieval fuses independent keyword and vector rankings with Reciprocal Rank Fusion (`k=60`). Optional `hybrid_rerank` applies a `RerankingProvider` interface; Phase 3 ships a deterministic lexical-overlap mock.
**Why:** Inspectable fusion scores; swappable real rerankers later without changing API shape.

---

## ADR-025 — Document content is untrusted data

**Status:** Accepted
**Decision:** Policy corpus text is never treated as instructions. Evidence is wrapped with an explicit DATA preamble; advisory injection patterns may flag review; tools remain on a separate allow-listed path from RAG.
**Why:** Contain prompt-injection from malicious or compromised documents without claiming a perfect scanner.

