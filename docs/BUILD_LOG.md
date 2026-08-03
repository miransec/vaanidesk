# VaaniDesk Build Log

Do not store secrets in this file.

## Environment (Phase 4 start)

| Item | Value |
|------|-------|
| Start commit | `a9a7f3379f5b07829b74e5bfedb1871d7b1706d0` |
| Expected prompt hash | `cf175b7` (actual tagged Phase 3 is `a9a7f33`) |
| Tag | `phase-3-complete` |
| Branch | `main` |
| Working tree | clean at Phase 4 start |
| Python | 3.12.13 (uv) |
| Node | v24.18.1 |
| Docker | 29.6.2 |

## Phase 4 — Secure multilingual voice

### Start
- Began from `phase-3-complete` / `a9a7f33`

### Migrations
- `0004_phase4_voice` (revision `0004_phase4`)

### Models added
- `VoiceMessage` — upload metadata, transcript, confirmation state
- `SpeechSynthesis` — TTS output records
- `VoiceTrace` — per-request audit/observability

### Components delivered
- `backend/app/voice/` — STT, TTS, validation, rate limiting, storage modules
- `backend/app/api/v1/voice.py` — full voice endpoint router
- `backend/app/services/voice.py` — service layer
- `backend/app/schemas/voice.py` — request/response models
- `docker-compose.test.yml` — isolated test Compose stack
- `backend/Dockerfile` — multi-stage runtime + test target
- `frontend/src/components/ChatPanel.tsx` — voice recording UI
- `sample_data/audio/` — fixture WAV files for tests

### Notes
- Voice is a transport into the existing controlled orchestrator
- Default STT/TTS providers are deterministic mocks (`DeterministicMockSTT`, `DeterministicMockTTS`)
- Audio stored on local filesystem via `AudioStorage` protocol (no S3 required)
- Transcript confirmation required before submitting sensitive intents
- Rate limiting per user (uploads/min, bytes/hour, STT/TTS reqs/min, concurrent jobs)

### Quality gates (Phase 4 completion)

| Check | Result |
|-------|--------|
| `uv run pytest -rs` | **86 passed, 0 skipped** |
| `ruff check .` | Pass |
| `ruff format --check .` | Pass |
| `python -m mypy app` | Pass |
| `npm run lint` | Pass |
| `npm run build` | Pass |
| Docker rebuild + health | Pass (backend healthy) |
| Migration cycle (down 0003 → up 0004) | Pass |
| Knowledge seed ×2 | `already_present` 17 docs / 241 chunks |

### Known limitations
- STT/TTS are deterministic mocks only — no real speech quality claims
- Audio storage is local filesystem; no S3 integration required for demo
- No production voice provider credentials needed

### Commit / tag
- Commit/tag filled after `git commit` / `git tag`

---

_Results appended at each phase checkpoint._
