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

## Phase 4 voice controls

| Control | Behavior |
|---------|----------|
| Audio ownership | Voice messages scoped to authenticated user; download/delete require ownership |
| Transcript confirmation | Sensitive intents require explicit transcript hash binding before submission |
| No raw audio in traces | Agent traces store transcript text and metadata only — never raw audio bytes |
| Rate limiting | Per-user: uploads/min, bytes/hour, STT reqs/min, TTS reqs/min, max concurrent jobs |
| Format validation | Only allowed MIME types (`wav`, `mp3`, `webm`, `m4a`); size and duration caps enforced |
| Storage retention | Audio files expire after `AUDIO_RETENTION_HOURS`; cleanup endpoint removes stale files |
| Edit invalidation | Editing a transcript invalidates prior confirmation — re-confirmation required |

## Phase 5 — Channel Security

| Control | Implementation |
|---------|---------------|
| HMAC signature verification | Constant-time compare, fail closed on missing/invalid signature |
| Timestamp tolerance | Reject webhooks with timestamps outside configurable window (default 300s) |
| Replay protection | Event ID + timestamp stored; duplicate signatures rejected |
| External confirmation | Sensitive write intents from channels require signed one-time web confirmation (not "yes" in chat) |
| Identity linking | One-time challenge token, single-use, expiring; unlink revokes access |
| Attachment validation | Size cap, MIME type check, executable extensions blocked |
| Cross-user attachment denial | Download authorization checks owner_user_id matches requesting user |
| Unlinked identity restriction | Cannot access account orders or perform sensitive actions |
| No secrets in logs | Webhook payloads, raw tokens, and full message bodies not logged at INFO |
| Human handoff | Auto-responses paused when conversation assigned to human agent |

## Verification

Phase 2 security suite remains green. Phase 3 adds cross-user restricted-doc denial, reranker isolation, malicious-doc tool non-execution, citation integrity, and multilingual policy chat tests. Phase 4 adds voice upload ownership, transcript confirmation for sensitive actions, rate limit enforcement, and audio retention/cleanup. Phase 5 adds HMAC verification, replay protection, external confirmation for sensitive channel actions, identity linking security, and attachment validation.

---

_Full professional threat model remains Phase 7._
