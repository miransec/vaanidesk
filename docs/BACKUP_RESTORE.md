# VaaniDesk — Backup & Restore

## Backup

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/vaanidesk \
  python -m scripts.backup --output-dir ./backups
```

Output: `backups/vaanidesk_YYYYMMDD_HHMMSS.sql.gz` (pg_dump custom format).

### Automated backups

Schedule via cron (daily at 02:00):

```cron
0 2 * * * cd /opt/vaanidesk/backend && DATABASE_URL=... python -m scripts.backup --output-dir /backups
```

In Docker:

```bash
docker compose -f docker-compose.prod.yml exec backend \
  python -m scripts.backup --output-dir /data/backups
```

## Restore

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/vaanidesk \
  python -m scripts.restore backups/vaanidesk_20260804_020000.sql.gz
```

This performs `pg_restore --clean --if-exists` and verifies with a user count query.

## Verification

After restore, verify:

```bash
curl http://localhost:8000/ready   # Should return {"status":"ok"}
# Check user count
psql -U vaanidesk -d vaanidesk -c "SELECT count(*) FROM users;"
# Check migration state
cd backend && uv run alembic current
```

## Retention Cleanup

Audio files, expired sessions, and confirmation tokens are cleaned by the retention script:

```bash
python -m scripts.retention_cleanup
```

Runs automatically in the `worker` container (docker-compose.prod.yml).

### Retention policies

| Data | Default retention | Configurable |
|------|------------------|-------------|
| Audio recordings | 72 hours | `AUDIO_RETENTION_HOURS` |
| Refresh sessions | 7 days (auto-expire) | `REFRESH_TOKEN_EXPIRE_DAYS` |
| Confirmation tokens | 10 minutes | `CONFIRMATION_TOKEN_TTL_SECONDS` |
| Idempotency records | 30 days | `IDEMPOTENCY_RECORD_TTL_DAYS` |
| Audit logs | Indefinite | Manual archival |

## Safe Dev Reset

```bash
docker compose down -v          # Destroy volumes
docker compose up -d postgres redis
cd backend
uv run alembic upgrade head
uv run python -m scripts.seed
```
