# Security

VaaniDesk treats security as a first-class product requirement: user isolation, allow-listed tools, confirmation for sensitive actions, upload validation, log redaction, and resistance to prompt injection (including indirect injection via retrieved documents).

## Documents

- **Threat model and controls:** [`docs/SECURITY.md`](./docs/SECURITY.md)
- **Architecture safety notes:** [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md)
- **Architectural decisions:** [`docs/ADR.md`](./docs/ADR.md)
- **Deployment hardening:** [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md)

## Reporting vulnerabilities

Please report security vulnerabilities **privately** to the maintainers. Do not open public GitHub issues for exploitable bugs until a fix is available.

Do not include production secrets, customer data, or live credentials in reports. Prefer redacted reproduction steps against a local mock stack.

## Non-negotiables

1. No API keys or tokens in source control.
2. Models cannot execute arbitrary functions or access the database directly.
3. Customers cannot read another customer’s orders, conversations, tickets, or private data.
4. Retrieved documents are untrusted data, not instructions.
5. Destructive or sensitive tools require confirmation tokens and durable idempotency records.
6. Mocks and simulators are labeled; optional integrations stay optional.
7. Redis security paths (confirmation, replay protection, sensitive AuthZ, security rate limits) fail closed.
8. Future MCP / Puch credentials and resume content must come from environment or file path only — never hardcoded. The MCP server package is not shipped in v1.0.0 application code.

Detailed mitigations live in [`docs/SECURITY.md`](./docs/SECURITY.md).
