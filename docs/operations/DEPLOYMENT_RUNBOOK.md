# Deployment Runbook — Atlas Paper V1

**Scope:** Continuous **paper** operation only. Live-money credentials must not be deployed.

## Architecture (runtime)

| Service | Role |
|---------|------|
| `api` | FastAPI + Alembic migrate-on-start + uvicorn |
| `postgres` | Durable paper state (accounts, orders, fills, analytics) |
| `redis` | Optional; not required for Paper V1 trading path |
| Frontend | Next.js ops dashboard (separate process or container) |

Canonical compose file: `docker-compose.yml`.

## Safe defaults

```bash
TRADING_MODE=paper
ENABLE_LIVE_TRADING=false
LIVE_TRADING_ENABLED=false
USE_LIVE_MARKET_DATA=false
ENABLE_TRADING_SCHEDULER=false   # enable explicitly after hydrate/recon healthy
ADMIN_API_TOKEN=<server-only secret>
ATLAS_AUTH_SECRET=<shared backend/frontend secret>
```

Never place exchange live API keys or `ADMIN_API_TOKEN` in frontend bundles.

## Bring-up

```bash
cp .env.example .env
# edit ADMIN_API_TOKEN / ATLAS_AUTH_SECRET; keep TRADING_MODE=paper

docker compose config          # validate
docker compose up -d postgres
docker compose up -d api       # runs: alembic upgrade head && uvicorn ...

# Frontend (host or container)
npm --prefix frontend ci
ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm --prefix frontend run build
ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm --prefix frontend run start
```

## Health / readiness

| Probe | Expectation |
|-------|-------------|
| `GET /health` | process up; includes kill-switch / mode flags |
| `GET /ready` | DB `SELECT 1` ok; LIVE runtime always not-ready |
| Frontend `/login` | HTTP 200 |

Fail-closed: unhealthy DB / failed reconciliation pauses trading.

## Scheduler

1. Confirm hydrate + reconciliation healthy (`GET /api/v1/recovery/status`).
2. Set `ENABLE_TRADING_SCHEDULER=true` only when intentional.
3. Scheduler resumes from persisted cycle keys; duplicate cycle IDs are idempotent.

## Restart

1. `docker compose restart api`
2. API re-runs migrations (no-op at head) and hydrates paper session.
3. Verify balances/positions/kill-switch via dashboard or `/api/portfolio`.

## Rollback

1. Stop scheduler / engage kill switch.
2. `docker compose stop api`
3. Restore DB from backup (see `BACKUP_RESTORE.md`).
4. Optionally `alembic downgrade -1` only when the latest revision is known-safe (0007 analytics supports downgrade).
5. Redeploy previous image/tag.

## Known non-goals

- No live broker instantiation for Paper V1.
- No futures / leverage / withdrawals / copy trading.
