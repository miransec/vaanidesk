# VaaniDesk screenshots (v1.0.1)

Real UI captures from the running Docker/local stack at annotated tag **v1.0.1** (`29379ba`).

Viewport: **1440×1000** CSS pixels, **deviceScaleFactor 2** → PNG **2880×2000**.

Persona for chat scenarios: **Aarav Sharma** (`demo-anya` internal key; UI shows display name + demo email only).

| File | Scenario | Persona | Message / query | Demonstrates |
|------|----------|---------|-----------------|--------------|
| `01-home.png` | Product homepage | — | — | Brand-first landing, Try the demo CTA, product vs Engineering nav, no phase/debug copy |
| `02-hinglish-order.png` | Hinglish order status | Aarav Sharma | `mera order VD-10021 kahan hai?` | Multilingual chat, customer-safe reply, structured order card, no raw tools/UUIDs |
| `03-order-status.png` | Order status card | Aarav Sharma | `where is my order VD-10021` | Customer-safe order result (number, status, delivery address) |
| `04-rag-refund-citations.png` | Damaged-product policy RAG | Aarav Sharma | `What is the refund policy for a damaged product?` | Grounded policy answer; expanded **Sources** led by Damaged Products Policy (not escalation playbooks); no raw evidence-confidence numbers |
| `05-cancellation-confirmation.png` | Sensitive cancel gate | Aarav Sharma | `please cancel my order VD-10022` | Customer confirmation card (**Keep order** / **Confirm cancellation**) before destructive action; captured then cancelled with Keep order so seed stays consistent |
| `06-support-escalation.png` | Unknown / unsupported escalation | Aarav Sharma | `blorp zarf 77777 please help me with something completely unknown` | Single-turn unknown intent → natural uncertainty + support request card (`TKT-*`, Open) + demo limitation; no prior RAG answer; no `Tool: transfer_to_human` |
| `07-observability.png` | Engineering observability | — (admin page) | Prior chat traffic reflected in aggregates | System overview (traces, tools, retrieval), counters, Prometheus metrics; engineering-facing (intent vs evidence confidence called out in page copy) |
| `08-evaluations.png` | Evaluation runs | — (admin page) | Live dataset/run list from DB | `vaanidesk-core-v1` (113 cases) and completed mock runs with pass rate / security status |

## Capture notes

- Stack: healthy backend, frontend, PostgreSQL, Redis; deterministic seed + curated personas only.
- Chat threads were cleared for Aarav between scenarios so each frame shows a focused exchange (environment prep only; no product code changes).
- Confirmation screenshot used **Keep order** afterward; curated order `VD-10022` remains **pending**.
- Do not fabricate UI or inject evaluation counts into the DOM.

## Capture helper (optional)

```bash
cd frontend
node scripts/capture-portfolio-screenshots.mjs
```

Requires Playwright browsers and a running stack at `http://localhost:3000`.
