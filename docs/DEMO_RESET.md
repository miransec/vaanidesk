# VaaniDesk demo reset (VPS)

Safe procedure to restore deterministic curated personas/orders without
redeploying containers.

```bash
cd /opt/vaanidesk
docker compose -f docker-compose.vps.yml --env-file .env.vps exec backend \
  uv run python -m scripts.seed --force
docker compose -f docker-compose.vps.yml --env-file .env.vps exec backend \
  uv run python -m scripts.seed_knowledge
```

`--force` truncates transactional demo tables and reseeds curated personas:

- Aarav Sharma (`demo-anya`)
- Rahul Verma (`demo-rahul`)
- Meera Patel (`demo-meera`)

Auth/test fixture users are not returned by `GET /api/v1/demo-users`.

After reset, confirm:

```bash
curl -sS https://vaanidesk.muhammadmiran.com/api/v1/demo-users | head
curl -sS https://vaanidesk.muhammadmiran.com/ready
```
