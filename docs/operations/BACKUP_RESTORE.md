# Backup & Restore — Atlas Paper V1

## What to back up

| Asset | Why |
|-------|-----|
| PostgreSQL volume / logical dump | Paper balances, positions, orders, fills, closed trades, reports, cycle keys |
| `.env` (secrets store) | Admin token + auth secret (store outside git) |
| Compose / image tag | Reproducible rollback |

Redis is optional for Paper V1 and is not the source of truth for balances.

## Logical backup (PostgreSQL)

```bash
docker compose exec -T postgres \
  pg_dump -U atlas -d atlas --format=custom \
  > "atlas-paper-$(date -u +%Y%m%dT%H%M%SZ).dump"
```

Plain SQL alternative:

```bash
docker compose exec -T postgres \
  pg_dump -U atlas -d atlas \
  > "atlas-paper-$(date -u +%Y%m%dT%H%M%SZ).sql"
```

## Restore

1. Engage kill switch and stop the API (prevent writes during restore).
2. Recreate or empty the database.
3. Restore:

```bash
docker compose exec -T postgres \
  pg_restore -U atlas -d atlas --clean --if-exists < atlas-paper-YYYYMMDD.dump
```

4. Start API (`alembic upgrade head` is idempotent at head).
5. Verify hydrate: portfolio cash/positions, kill-switch, last cycle, analytics trade count.
6. Clear reconciliation halt only after totals match (`CLEAR_RECONCILIATION_HALT` + admin token).

## SQLite (dev only)

```bash
cp atlas.db "atlas-$(date -u +%Y%m%dT%H%M%SZ).db"
```

Restore by replacing the file while the API is stopped, then `alembic upgrade head`.

## Verification checklist

- [ ] `alembic_version` = `0007_perf_analytics` (or current head)
- [ ] `paper_accounts` / checkpoint cash matches pre-backup
- [ ] Open positions quantities match
- [ ] `closed_trades` count matches
- [ ] Kill-switch flag restored
- [ ] Duplicate cycle replay remains idempotent
