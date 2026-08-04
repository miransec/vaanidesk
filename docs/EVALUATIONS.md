# VaaniDesk — Evaluation Framework

## Overview

Phase 6 introduces a deterministic evaluation framework for assessing VaaniDesk's capabilities across all system features (chat, RAG, voice, channels) in a CI-friendly, reproducible manner.

## Mock vs Real Separation

**Current state:** All evaluations run against the **mock provider**. Scores reflect deterministic mock behavior and structural correctness — they do **not** measure real LLM quality, STT accuracy, or semantic understanding.

| Aspect | Mock Evaluation | Real Evaluation (future) |
| --- | --- | --- |
| Provider | `mock` | `openai` / `anthropic` |
| Deterministic | Yes (same seed → same results) | No (model variance) |
| Cost | Free | Token-based pricing |
| Measures | Routing, tool selection, security gates, pipeline integrity | Response quality, language understanding, hallucination |
| CI suitability | Primary use case | Scheduled / manual |
| Scores meaning | Structural pass/fail | Semantic quality |

## Dataset

The core dataset (`vaanidesk-core-v1`) contains **113 cases** covering:

### Languages
- English (en), Hindi (hi), Marathi (mr), Hinglish (code-mixed), Unknown

### Categories (21)
- `greetings` — multilingual greeting handling
- `order_status` — order lookup, tracking
- `ownership_denial` — cross-user access prevention (security-critical)
- `cancel_eligibility` — cancellation rule enforcement
- `cancel_confirm` — confirmation flow for high-risk actions (security-critical)
- `cancel_idempotency` — duplicate prevention
- `tickets` — support ticket creation/lookup
- `escalation` — human handoff triggers
- `policy_retrieval` — knowledge base retrieval with citations
- `citation_correctness` — citation accuracy, no fabrication (security-critical)
- `no_answer` — out-of-scope handling
- `restricted_doc_denial` — access control enforcement (security-critical)
- `prompt_injection` — jailbreak/injection resistance (security-critical)
- `malicious_retrieved_instruction` — data-plane injection defense (security-critical)
- `voice_transcript_review` — voice pipeline handling
- `low_confidence_voice` — low-confidence transcript behavior
- `channel_dedup` — message deduplication
- `identity_linking` — channel identity linking flow
- `external_sensitive_confirm` — external channel confirmation (security-critical)
- `malformed_unsupported_input` — XSS, SQLi, edge cases
- `rate_limiting` — throttling behavior

### Security-Critical Cases
~30 cases marked `security_critical: true` with explicit `security_expectations`. A single security failure causes the entire run to **fail**.

Security failure types:
- Ownership leak (cross-user data access)
- Unauthorized write (write without proper auth)
- Confirmation bypass (skipping required confirmation)
- Fabricated citation (hallucinated document references)
- Duplicate sensitive write (double-execution of idempotent operations)

## Running Evaluations

### CLI
```bash
cd backend
uv run python -m scripts.run_evaluations --provider mock --seed 42
uv run python -m scripts.run_evaluations --output-dir ./eval_results
```

### API
```bash
# Seed dataset
curl -X POST http://localhost:8000/api/v1/evaluations/datasets/seed \
  -H "X-Demo-User-Key: demo-anya"

# Start run
curl -X POST http://localhost:8000/api/v1/evaluations/runs \
  -H "X-Demo-User-Key: demo-anya" \
  -H "Content-Type: application/json" \
  -d '{"dataset_name": "vaanidesk-core-v1", "provider": "mock", "seed": 42}'

# Export results
curl http://localhost:8000/api/v1/evaluations/runs/{run_id}/export?fmt=json \
  -H "X-Demo-User-Key: demo-anya"
```

### Admin UI
Navigate to `/admin/evaluations` in the frontend.

## Comparison & Regression

Each run automatically compares against the most recent previous completed run. A regression is flagged when pass rate drops by >5%.

## Export Formats

- **JSON**: Full structured data including per-case results
- **Markdown**: Human-readable summary with category breakdown table

## Observability

### OpenTelemetry
- Console/no-op exporter by default
- Configure `OTEL_EXPORTER_OTLP_ENDPOINT` for production collectors
- Trace attributes: request IDs, durations, language, provider, model — NO raw tokens, secrets, audio, or private reasoning

### Prometheus Metrics
- Endpoint: `GET /metrics`
- Format: Prometheus text exposition (0.0.4)
- No high-cardinality labels (no raw user IDs)

### Structured Logging
- Redaction filters prevent secrets from entering log output
- Tests verify: API keys, Bearer tokens, body content all redacted
