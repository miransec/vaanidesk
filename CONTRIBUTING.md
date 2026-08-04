# Contributing to VaaniDesk

## Development Setup

1. Clone the repository
2. Copy `.env.example` to `.env`
3. Start infrastructure: `docker compose up -d postgres redis`
4. Backend: `cd backend && uv sync --extra dev && uv run alembic upgrade head && uv run python -m scripts.seed`
5. Frontend: `cd frontend && npm ci && npm run dev`

## Code Standards

### Backend (Python)
- Python 3.12+
- Formatter/linter: `ruff` (check: `uv run ruff check .`, format: `uv run ruff format .`)
- Type checking: `uv run python -m mypy app`
- Tests: `uv run pytest -rs`

### Frontend (TypeScript)
- Node 24+
- Linter: `npm run lint`
- Typecheck: `npm run typecheck`
- Build check: `npm run build`
- Browser E2E: `npx playwright install chromium` then `npm run test:e2e` (stack must be running)

## Testing

- All tests must pass with `LLM_PROVIDER=mock` (no paid APIs required)
- New features require tests
- No required skips — all tests must pass
- Test database is isolated (`docker-compose.test.yml` or separate PG instance)
- Playwright covers critical chat/auth paths only — keep new E2E cases small and deterministic

## Commit Messages

Format: `type: description`

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

## Security

### Reporting Vulnerabilities

Please report security vulnerabilities privately via email to the maintainers.
Do not open public issues for security bugs.

### Rules

- Never commit real API keys, passwords, or secrets
- Use `.env` for local configuration
- All auth-related changes require security review
- Passwords must use Argon2id hashing with pepper
- No `localStorage` for credentials
