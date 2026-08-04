# VaaniDesk — Deployment Guide

## Prerequisites

- Docker and Docker Compose v2+
- A domain name (for HTTPS via Caddy)
- PostgreSQL 16 with pgvector extension
- Redis 7+

## Production Deployment

### 1. Configure environment

Copy `.env.example` to `.env` and set all production values:

```bash
cp .env.example .env
# Edit .env — set strong secrets, real domain, disable debug
```

**Required production settings:**

| Variable | Requirement |
|----------|------------|
| `SECRET_KEY` | Min 32 random chars, not placeholder |
| `JWT_SECRET_KEY` | Min 32 random chars, not placeholder |
| `PASSWORD_PEPPER` | Min 16 random chars, not placeholder |
| `SECURE_COOKIES` | `true` |
| `DEBUG` | `false` |
| `APP_ENV` | `production` |
| `CORS_ORIGINS` | Explicit origin(s), no wildcard |
| `TRUSTED_HOSTS` | Your domain(s) |

Generate secrets: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

### 2. Update Caddyfile

Edit `deploy/Caddyfile` — replace `app.example.com` with your domain.

### 3. Deploy

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### 4. Run migrations

```bash
docker compose -f docker-compose.prod.yml exec backend uv run alembic upgrade head
```

### 5. Seed data (optional)

```bash
docker compose -f docker-compose.prod.yml exec backend uv run python -m scripts.seed
```

### 6. Verify

```bash
curl https://your-domain.com/health
curl https://your-domain.com/ready
```

## Architecture

```
Internet → Caddy (HTTPS/TLS) → Backend (FastAPI :8000)
                               → Frontend (Next.js :3000)
Backend → PostgreSQL :5432 (internal only)
        → Redis :6379 (internal only)
Worker  → PostgreSQL / Redis (retention cleanup)
```

## Container Security

- Multi-stage builds (minimal runtime, no dev tools)
- Non-root user (`appuser`, UID 10001)
- Read-only filesystem where practical
- No PG/Redis ports exposed publicly
- Pinned base image versions
- Health checks on all services
- Graceful shutdown via SIGTERM

## Migration Procedure

1. Back up the database: `python -m scripts.backup`
2. Deploy new containers
3. Run migrations: `alembic upgrade head`
4. Verify with `/ready`
5. If issues: `alembic downgrade -1` then restore from backup

## Secret Rotation

1. Generate new secret
2. Update in `.env` or secret manager
3. Restart affected service
4. JWT rotation: old tokens expire naturally (15 min access, 7 day refresh)
5. Password pepper rotation: requires re-hashing all passwords (coordinate carefully)

## Monitoring

- `/health` — liveness
- `/ready` — readiness (checks DB + Redis)
- `/metrics` — Prometheus-compatible metrics
- Structured JSON logs to stdout
