# Security Threat Model (VaaniDesk)

**Status:** Phase 3 controls documented; full threat model still lands in **Phase 7**.

## Goals

Protect customer data isolation, prevent unauthorized tool execution, contain prompt-injection impact, and avoid secret leakage in logs or responses.

## Phase 2 controls in force

| Control | Behavior |
|---------|----------|
| Demo auth | Header-based only — **not** production authentication |
| Order AuthZ | Tools require `user_id` + public order ref (`VD-*`); ref-only lookup forbidden |
| Ticket AuthZ | Same ownership rule for `TKT-*` |
| Allow-listed tools | Unregistered tool names never execute |
| Confirmation | High-risk tools need Redis tokens |
| Token binding | User + tool + argument hash; single-use; TTL; SHA-256 at rest |
| Redis fail-closed | Confirmation create/consume returns `503` if Redis is down |
| Idempotency | Durable Postgres records for state-changing tools |
| Redaction | Tool argument summaries redact token-like keys |

## Phase 3 knowledge controls

| Control | Behavior |
|---------|----------|
| Document access levels | `public`, `authenticated`, `restricted` (+ JSON allowlist of `demo_key`) |
| Retrieval AuthZ | SQL filter before candidates leave Postgres |
| Tool isolation | Retrieved evidence never selects or executes tools |
| Evidence delimiters | Untrusted DATA preamble + `<EVIDENCE>` wrappers |
| Injection scanner | **Advisory only** — does not claim complete coverage |
| Citations | Only retrieved chunk IDs; no fabricated titles |
| Traces | Store IDs/scores/citation titles — not unauthorized full text |
| Upload safety | Reject unsupported MIME + oversized bodies; never execute document contents |

## Redis policy

| Use | If Redis unavailable |
|-----|----------------------|
| Optional caches | Degrade |
| Confirmation tokens | **Fail closed** |

## Verification

Phase 2 security suite remains green. Phase 3 adds cross-user restricted-doc denial, reranker isolation, malicious-doc tool non-execution, citation integrity, and multilingual policy chat tests.

---

_Full professional threat model remains Phase 7._
