# VaaniDesk â€” Task Tracker

Last updated: 2026-08-04 (Phase 4 complete)

Legend: `[ ]` todo Â· `[~]` in progress Â· `[x]` done Â· `[-]` blocked Â· `[!]` risk

**Default branch:** `main`
**Tags:** `phase-1-complete`, `phase-2-complete`, `phase-3-complete`
**Phase 3:** complete
**Phase 4:** complete (86 tests passed, 0 skipped) â€” commit pending

---

## Phase 0 â€” Environment and planning

- [x] Completed and approved

---

## Phase 1 â€” Working foundation

- [x] Completed, committed, tagged `phase-1-complete`

---

## Phase 2 â€” Agent and tools

- [x] Completed, committed, tagged `phase-2-complete`

---

## Phase 3 â€” Knowledge / RAG

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


| Check                                 | Result                                           |
| ------------------------------------- | ------------------------------------------------ |
| `uv run pytest -rs`                   | **64 passed, 0 skipped**                         |
| Knowledge totals before â†’ after suite | **17 / 23 / 241** unchanged                      |
| Seed run 1 / run 2 (Docker)           | `already_present` 17 docs / 241 chunks both runs |
| `ruff check .`                        | Pass                                             |
| `ruff format --check .`               | Pass                                             |
| `python -m mypy app`                  | Pass                                             |
| `npm run lint`                        | Pass                                             |
| `npm run build`                       | Pass                                             |
| `docker compose ps`                   | All up; backend/postgres/redis healthy           |


**Not in Phase 3:** voice, images, WhatsApp, MCP, full eval suites, public deployment

---



## Phase 4 â€” Secure multilingual voice

- [x] Alembic migration `0004_phase4_voice` (models: VoiceMessage, SpeechSynthesis, VoiceTrace)
- [x] Voice module (`backend/app/voice/`) â€” STT, TTS, validation, rate limiting, storage
- [x] Voice API router `/api/v1/voice` â€” upload, transcribe, confirm, edit, submit, TTS, download, cleanup
- [x] DeterministicMockSTT + DeterministicMockTTS providers
- [x] AudioStorage local filesystem (configurable retention, size/duration limits)
- [x] Transcript confirmation flow (required for sensitive intents before submit)
- [x] Per-user rate limiting (uploads/min, bytes/hour, STT/TTS reqs/min, concurrent jobs)
- [x] Frontend ChatPanel voice recording UI
- [x] `docker-compose.test.yml` for isolated test runs
- [x] Backend Dockerfile multi-stage (runtime + test targets)
- [x] Audio test fixtures (`sample_data/audio/`)
- [x] 86 tests passed, 0 skipped
- [x] Quality gates: ruff check, ruff format, mypy, frontend lint + build all pass

---

## Phase 5 â€” MCP (not started)

- [ ] Deferred until Phase 4 commit

---



## Open blockers


| ID  | Blocker                                                                | Needed for | Owner |
| --- | ---------------------------------------------------------------------- | ---------- | ----- |
| B6  | `uv run mypy` shim blocked by App Control; use `uv run python -m mypy` | Documented | â€”     |


---



## Notes

- Confirmation Redis key = `vd:confirm:` + SHA-256(raw token); payload omits raw token.
- RAG embeddings are deterministic lexical mocks â€” not production semantic embeddings.
- Access control filters apply in SQL before candidates leave Postgres.
- Restricted corpus doc `Internal Override Notes` allowlists `demo-anya` only (injection bait).
- Knowledge seed: Compose `KNOWLEDGE_SEED_DIR=/sample_data/policies` with `./sample_data:/sample_data:ro`.
- Phase 2 order helpers re-arm pending/confirmed status instead of skipping when prior cancels exhausted stock.
- Phase 3 ingest tests use `__vdtest__` titles + `isolated_knowledge` cleanup so the demo corpus is not polluted.
- Phase 4 voice STT/TTS are deterministic mocks â€” not real speech providers.
- Phase 4 audio fixtures in `sample_data/audio/` (WAV files for en, hi, hinglish, mr, malformed, low_confidence, unknown).
- Voice transcript confirmation binds SHA-256 hash; edit invalidates prior confirmation.
