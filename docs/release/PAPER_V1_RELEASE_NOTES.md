# Project Atlas Paper V1 — Release Notes

**Version:** `v1.0.0-paper`  
**Title:** Project Atlas Paper V1  
**Branch:** `release/atlas-paper-v1` (PR #34)  
**Includes:** PR #35 paper performance analytics

## Summary

Paper V1 is a personal, deterministic **paper-trading** platform. Live-money execution remains hard-blocked.

## Highlights

- Single authoritative cycle path: market data → strategy → `OrderGateway` → risk engine → paper engine → persistence → analytics → API/dashboard
- Durable paper balances, positions, orders, fills, sessions, kill-switch, cycle keys
- Restart hydration + fail-closed reconciliation
- Performance analytics: closed trades, ROI/PnL/fees/win rate/drawdown, equity history, CSV/JSON export, mobile `/performance` + `/trades`
- Alembic chain `0001` → `0007_perf_analytics`
- Admin-authenticated mutators; secrets stay server-side

## Safety model

- Default `TRADING_MODE=paper`
- `LiveTradingGate.allowed` is always `false` in this release
- Kill switch blocks new orders; read-only monitoring remains available
- Duplicate cycle IDs / exchange-event style idempotency prevent duplicate orders/fills on the paper path

## Not in scope

- Live-money trading readiness
- Futures, leverage, copy trading, customer accounts, withdrawals
- High-frequency or autonomous AI execution

## Operations

See:

- `docs/operations/DEPLOYMENT_RUNBOOK.md`
- `docs/operations/BACKUP_RESTORE.md`
- `docs/operations/INCIDENT_RESPONSE.md`
- `docs/release/PAPER_V1_ACCEPTANCE_REPORT.md`
- `docs/release/PAPER_V1_PR_AUDIT.md`
