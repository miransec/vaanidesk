# VaaniDesk — Task Tracker

Last updated: 2026-08-04 (Phase 3 final closeout)

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` blocked · `[!]` risk

**Default branch:** `main`  
**Tags:** `phase-1-complete`, `phase-2-complete`  
**Phase 3:** final closeout verified — awaiting review (do **not** start Phase 4)

---

## Phase 0 — Environment and planning

- [x] Completed and approved

---

## Phase 1 — Working foundation

- [x] Completed, committed, tagged `phase-1-complete`

---

## Phase 2 — Agent and tools

- [x] Completed, committed, tagged `phase-2-complete`

---

## Phase 3 — Knowledge / RAG

- [x] Models + Alembic `0003_phase3_knowledge`
- [x] Sample multilingual policy corpus + idempotent seed
- [x] Ingestion (md/text/json), chunking, mock embeddings, FTS + pgvector
- [x] Keyword / vector / hybrid (RRF) / hybrid+rerank retrieval
- [x] In-SQL access control; citations; no-answer; injection advisory
- [x] Knowledge APIs + `/knowledge` UI; chat citations
- [x] Docker seed-path fix (`KNOWLEDGE_SEED_DIR` + `/sample_data` mount)
- [x] Test isolation (cleanup fixtures; demo corpus unchanged after suite)
- [x] Unauthorized restricted-doc absent from candidates/selected/rerank/trace/citations/context
- [x] Final quality gates (2026-08-04)

### Final closeout results (2026-08-04)

| Check | Result |
|-------|--------|
| `uv run pytest -rs` | **64 passed, 0 skipped** |
| Knowledge totals before → after suite | **17 / 23 / 241** unchanged |
| Seed run 1 / run 2 (Docker) | `already_present` 17 docs / 241 chunks both runs |
| `ruff check .` | Pass |
| `ruff format --check .` | Pass |
| `python -m mypy app` | Pass |
| `npm run lint` | Pass |
| `npm run build` | Pass |
| `docker compose ps` | All up; backend/postgres/redis healthy |

**Not in Phase 3:** voice, images, WhatsApp, MCP, full eval suites, public deployment

---

## Phase 4 — (not started)

- [ ] Deferred until Phase 3 review approval

---

## Open blockers

| ID | Blocker | Needed for | Owner |
|----|---------|------------|-------|
| B6 | `uv run mypy` shim blocked by App Control; use `uv run python -m mypy` | Documented | — |

---

## Notes

- Confirmation Redis key = `vd:confirm:` + SHA-256(raw token); payload omits raw token.
- RAG embeddings are deterministic lexical mocks — not production semantic embeddings.
- Access control filters apply in SQL before candidates leave Postgres.
- Restricted corpus doc `Internal Override Notes` allowlists `demo-anya` only (injection bait).
- Knowledge seed: Compose `KNOWLEDGE_SEED_DIR=/sample_data/policies` with `./sample_data:/sample_data:ro`.
- Phase 2 order helpers re-arm pending/confirmed status instead of skipping when prior cancels exhausted stock.
- Phase 3 ingest tests use `__vdtest__` titles + `isolated_knowledge` cleanup so the demo corpus is not polluted.
