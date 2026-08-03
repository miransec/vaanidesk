# Security Threat Model (VaaniDesk)

**Status:** Phase 0 stub — full threat model, abuse cases, and control mapping land in **Phase 7**.

## Goals

Protect customer data isolation, prevent unauthorized tool execution, contain prompt-injection impact, and avoid secret leakage in logs, MCP responses, or the public dashboard.

## Threat categories (to be detailed in Phase 7)

| Area | Examples |
|------|----------|
| Prompt injection | User message overrides; indirect injection in policy docs |
| Tool abuse | Argument manipulation; excessive permissions; missing confirmation |
| Data isolation | IDOR on order IDs; cross-user MCP scope breaks |
| Upload abuse | Malicious files; bad MIME; oversized payloads |
| Channel abuse | Webhook replay; duplicate events |
| Availability / cost | Rate-limit abuse; denial-of-wallet via huge contexts |
| Supply chain | Dependency vulnerabilities |

## Controls (planned)

Input/output validation, allow-listed tools, per-tool AuthZ, confirmation tokens, durable idempotency records for sensitive mutations, rate limits, request-size caps, upload validation, log redaction, untrusted-document delimiters, timeouts/retries/circuit breakers, secure defaults.

Redis: optional caches may degrade; confirmation tokens, replay protection, sensitive-action AuthZ, and security rate limits **fail closed** when Redis is unavailable.

Puch MCP: never hardcode `PUCH_APPLICATION_KEY`, `PUCH_PHONE_NUMBER`, or resume Markdown contents.

## Verification

Automated tests will include: cross-user order access denial, refund/cancel without confirmation denied, prompt-injection text in a policy document cannot force an unrelated tool, invalid MCP token rejected, MCP cross-user attempt denied.

---

_This file will be rewritten into a full professional threat model during Phase 7 production hardening._
