# VaaniDesk Architecture

**Phase:** 2 (controlled agent workflow + business tools)
**Companion docs:** [`../PLAN.md`](../PLAN.md), [`../TASKS.md`](../TASKS.md), [`ADR.md`](./ADR.md), [`API.md`](./API.md)

---

## Phase 2 agent workflow

```mermaid
flowchart TD
  A[Receive chat message] --> B[Demo auth]
  B --> C[Normalize + conversation]
  C --> D[Detect language/script]
  D --> E[Classify intent + entities]
  E --> F{Missing fields?}
  F -->|yes| G[Clarification response]
  F -->|no| H{Confidence OK?}
  H -->|no| I[Escalate via transfer_to_human]
  H -->|yes| J[Select allow-listed tool]
  J --> K[Validate args + AuthZ]
  K --> L{High risk?}
  L -->|yes| M[Create Redis confirmation]
  M --> N[confirmation_required]
  L -->|no| O[Idempotency check]
  O --> P[Execute tool]
  P --> Q[Grounded multilingual response]
  Q --> R[Persist AgentTrace + ToolExecution]
```

## Confirmation flow

```mermaid
sequenceDiagram
  participant U as User
  participant API as FastAPI
  participant W as Workflow
  participant R as Redis
  participant DB as Postgres
  U->>API: cancel order VD-10001
  API->>W: run_support_workflow
  W->>R: SET confirm token TTL
  W-->>U: confirmation_required + summary
  U->>API: POST /actions/confirm approved
  API->>R: GET AuthZ DELETE token
  API->>DB: idempotency + cancel_order
  API-->>U: cancelled + trace
```

## Tool execution flow

```mermaid
flowchart LR
  Intent --> Registry
  Registry -->|unknown name| Reject
  Registry -->|known| Validate
  Validate --> Ownership
  Ownership -->|fail| NotFound
  Ownership -->|ok| Risk
  Risk -->|high| Confirm
  Risk -->|low/mod| Idempotency
  Confirm --> Idempotency
  Idempotency --> Handler
  Handler --> Trace
```

## Cross-user authorization boundary

```mermaid
flowchart TB
  subgraph caller [Authenticated demo user]
    U1[User A]
  end
  subgraph store [Data]
    OA[Order VD-10001 owner A]
    OB[Order VD-10005 owner B]
  end
  U1 -->|"user_id + VD-10001"| OA
  U1 -->|"user_id + VD-10005"| X[404 order_not_found]
  OB -.->|never returned| U1
```

## Design principles

1. Controlled workflow — explicit steps, not an unbounded autonomous agent loop
2. Allow-listed tools only
3. User-data isolation — ownership checks in tool/service layer
4. Fail closed on Redis security paths
5. Idempotent sensitive mutations
6. Honest demos — no fake live human agents

## Language detector limitations

Heuristic script + cue matching for `en` / `hi` / `hinglish` / `mr` / `unknown`. Not a production language model. Replaceable via `LanguageDetector` protocol.

## Intent taxonomy

`greeting`, `order_status`, `order_details`, `update_delivery_address`, `cancellation_eligibility`, `cancel_order`, `create_support_ticket`, `support_ticket_status`, `human_escalation`, `unknown`

## Tool registry (Phase 2)

| Tool | Risk | Confirmation | Idempotency |
|------|------|--------------|-------------|
| get_order_status | low | no | no |
| get_order_details | moderate | no | no |
| update_delivery_address | high | yes | yes |
| check_cancellation_eligibility | low | no | no |
| cancel_order | high | yes | yes |
| create_support_ticket | moderate | no | yes |
| get_support_ticket_status | low | no | no |
| transfer_to_human | moderate | no | yes |

Later phases add RAG, multimodal, MCP, and evals — see PLAN.md.
