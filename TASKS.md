# VaaniDesk — Task Tracker

Last updated: 2026-08-04 (Phase 4 complete; Phase 5 in progress)

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` blocked · `[!]` risk

**Default branch:** `main`
**Tags:** `phase-1-complete`, `phase-2-complete`, `phase-3-complete`, `phase-4-complete`
**Phase 3:** complete
**Phase 4:** complete (`0e05e4c`, tag `phase-4-complete`) — 86 tests passed, 0 skipped
**Phase 5:** in progress

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

- [x] Completed, committed, tagged `phase-3-complete`

---

## Phase 4 — Secure multilingual voice

- [x] Models + Alembic `0004_phase4` (VoiceMessage, SpeechSynthesis, VoiceTrace)
- [x] AudioStorage local FS + validation + rate limits
- [x] DeterministicMockSTT / DeterministicMockTTS
- [x] Transcript review/confirm/edit/submit through orchestrator
- [x] Voice API + ChatPanel voice UI + fixtures
- [x] docker-compose.test.yml + multi-stage Dockerfile
- [x] Quality gates: 86 passed, 0 skipped; ruff/mypy/frontend/Docker green
- [x] Commit `0e05e4c`, tag `phase-4-complete`

---

## Phase 5 — Omnichannel communication

- [~] Channel adapter boundary + models + migration
- [ ] Email + WhatsApp-compatible adapters (dev simulators)
- [ ] Identity linking + external sensitive confirmation
- [ ] Outbox / delivery retries / human handoff
- [ ] Operator channel UI
- [ ] Tests + quality gates + commit/tag

---

## Open blockers

| ID  | Blocker                                                                | Needed for | Owner |
| --- | ---------------------------------------------------------------------- | ---------- | ----- |
| B6  | `uv run mypy` shim blocked by App Control; use `uv run python -m mypy` | Documented | —     |

---

## Notes

- Confirmation Redis key = `vd:confirm:` + SHA-256(raw token); payload omits raw token.
- RAG embeddings are deterministic lexical mocks — not production semantic embeddings.
- Access control filters apply in SQL before candidates leave Postgres.
- Restricted corpus doc `Internal Override Notes` allowlists `demo-anya` only (injection bait).
- Knowledge seed: Compose `KNOWLEDGE_SEED_DIR=/sample_data/policies` with `./sample_data:/sample_data:ro`.
- Phase 2 order helpers re-arm pending/confirmed status instead of skipping when prior cancels exhaust stock.
- Phase 3 ingest tests use `__vdtest__` titles + `isolated_knowledge` cleanup so the demo corpus is not polluted.
- Phase 4 voice STT/TTS are deterministic mocks — not real speech providers.
- Phase 4 audio fixtures in `sample_data/audio/`.
- Voice transcript confirmation binds SHA-256 hash; edit invalidates prior confirmation.
- Phase 3 expected prompt hash `cf175b7` mismatched actual tagged commit `a9a7f33` — proceeded from actual tag.
