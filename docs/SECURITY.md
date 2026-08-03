# Security Threat Model (VaaniDesk)

**Status:** Phase 2 controls documented; full threat model still lands in **Phase 7**.

## Goals

Protect customer data isolation, prevent unauthorized tool execution, contain prompt-injection impact, and avoid secret leakage in logs or responses.

## Phase 2 controls in force

| Control | Behavior |
|---------|----------|
| Demo auth | Header-based only — **not** production authentication |
| Order AuthZ | Tools require `user_id` + public order ref (`VD-*`); ref-only lookup forbidden |
| Ticket AuthZ | Same ownership rule for `TKT-*` |
| Allow-listed tools | Unregistered tool names never execute |
| Confirmation | High-risk tools (`cancel_order`, `update_delivery_address`) need Redis tokens |
| Token binding | User + tool + argument hash + order; single-use; TTL |
| Token secrecy | Never logged; never placed in URLs |
| Redis fail-closed | Confirmation create/consume returns `503` if Redis is down |
| Idempotency | Durable Postgres records for state-changing tools |
| Redaction | Tool argument summaries redact token-like keys |
| Escalation honesty | Human handoff queues a ticket; never claims a live agent joined |

## Redis policy

| Use | If Redis unavailable |
|-----|----------------------|
| Optional caches | Degrade |
| Confirmation tokens | **Fail closed** |
| Sensitive-action AuthZ state | **Fail closed** |

## Verification (Phase 2 tests)

Automated coverage includes:

- Cross-user order/ticket access denial at **tool layer** (bypassing routers)
- Public `VD-*` ref alone never returns another user's order
- Cancel/address require confirmation; delivered orders cannot cancel
- Confirmation tokens stored as **SHA-256 digests** (raw token not Redis key / not in payload)
- Expired, reused, and cross-user tokens rejected (cross-user does not consume)
- Redis unavailable → HTTP **503** on confirmation create and execute; order status unchanged
- Duplicate idempotency keys replay once; arg mismatch → 409; concurrent inserts → single winner
- AgentTrace / ToolExecution redact tokens and truncate long addresses
- Frontend chat uses the same confirm API contract (approve / deny / error surfacing)

Reproducibility helper: `uv run python -m scripts.verify_phase2_refs`

Migration cycle proven: `alembic downgrade 0001_phase1` → `upgrade head` (repeated); order refs remain `VD-10001+` unique/contiguous.

---

_Full professional threat model remains Phase 7._
