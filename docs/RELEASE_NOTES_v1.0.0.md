# VaaniDesk v1.0.0 — Release Notes

**Tag:** `v1.0.0`  
**Date:** 2026-08-04  

## What VaaniDesk is

VaaniDesk is a production-oriented multilingual AI customer-support platform for a fictional e-commerce company. It demonstrates controlled tool-calling agents, hybrid RAG with citations, sensitive-action confirmation, authentication and authorization, omnichannel simulators, evaluations, and observability — all runnable locally with **deterministic mock providers**.

## Major capabilities

- Multilingual chat (English, Hindi, Marathi, Hinglish / code-switching)
- Controlled agent workflow: language → intent → allow-listed tools or RAG → AuthZ → confirmation → traces
- Business tools: order status/details, address update, cancel eligibility/cancel, tickets, human queue
- Hybrid knowledge retrieval (FTS + pgvector + RRF), citations, configurable no-answer
- Voice transport: audio upload, mock STT, transcript review, mock TTS
- Omnichannel adapters: email inbox simulator, WhatsApp simulator, HMAC webhooks, identity linking
- Production-shaped auth: Argon2id + pepper, JWT access, refresh rotation with reuse detection, roles
- Evaluations: 113-case dataset with security-critical fail-closed scoring
- Observability: Prometheus metrics, OTel hooks, structured logging with secret redaction
- Delivery: Docker Compose (dev + prod sketch), Alembic 0001–0007, GitHub Actions CI, Playwright E2E

## Architecture highlights

- FastAPI service layer with explicit ownership checks
- Provider abstraction defaulting to mocks (LLM / STT / TTS / embeddings)
- Redis used for confirmation, replay protection, and security-sensitive rate paths (fail closed)
- Next.js App Router UI for chat, knowledge, channels, account, and admin eval/observability

## Security highlights

- Cross-user order denial and restricted tool execution
- Confirmation tokens, replay rejection, idempotent destructive actions
- JWT / refresh rotation and refresh reuse detection
- CSRF / Origin validation for cookie-authenticated mutations
- Prompt-injection boundaries and retrieved-content tool isolation
- Webhook HMAC validation and replay protection
- Log redaction filters for secrets

## Evaluation and testing evidence

| Evidence | Result |
|----------|--------|
| Backend automated tests | 197 passed, 0 skipped |
| Deterministic evaluations (mock) | 113 / 113 passed |
| Security-critical evaluation cases | 40 cases, 0 failures |
| Playwright E2E | 9 passed |
| mypy | 0 errors (100 files) |
| Ruff / frontend lint / production build | pass |

## Mock / optional integrations

**Mock by default:** LLM workflow responses, STT, TTS, lexical embeddings, email simulator, WhatsApp simulator.

**Optional / credential-dependent:** real OpenAI-compatible LLM, cloud speech, WhatsApp Cloud API, SMTP, public deployment with real secrets.

## Known limitations

- Mock provider scores are **not** claims of production LLM accuracy
- Dedicated vision / image-understanding pipeline is not shipped (attachment validation + policy RAG only)
- MCP Streamable HTTP server for Puch is documented/planned — **not** present as application code in v1.0.0
- No public multi-tenant deployment is included with this tag
- Rate limiting and alerting are intentionally scoped for demo/dev; wire production notifiers yourself

## Upgrade / install

See root [`README.md`](../README.md) and [`docs/DEMO.md`](./DEMO.md).
