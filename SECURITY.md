# Security

VaaniDesk treats security as a first-class product requirement: user isolation, allow-listed tools, confirmation for sensitive actions, upload validation, log redaction, and resistance to prompt injection (including indirect injection via retrieved documents).

## Documents

- **Threat model and controls:** [`docs/SECURITY.md`](./docs/SECURITY.md)
- **Architecture safety notes:** [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- **Architectural decisions:** [`docs/ADR.md`](./docs/ADR.md)
- **Deployment hardening:** [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md) (Phase 7)

## Non-negotiables

1. No API keys or tokens in source control.
2. Models cannot execute arbitrary functions or access the database directly.
3. Customers cannot read another customer’s orders, conversations, tickets, or private data.
4. Retrieved documents are untrusted data, not instructions.
5. Destructive or sensitive tools require confirmation tokens and durable idempotency records.
6. Mocks and simulators are labeled; optional integrations stay optional.
7. Redis security paths (confirmation, replay protection, sensitive AuthZ, security rate limits) fail closed.
8. Puch MCP credentials and resume content come from environment / file path — never hardcoded.

Detailed mitigations and test plans are expanded in Phase 7; Phase 0 records intent only.
