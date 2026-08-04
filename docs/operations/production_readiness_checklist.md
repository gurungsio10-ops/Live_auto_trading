# Production readiness checklist — personal paper/testnet engine

**Live money trading must remain disabled until every item below passes AND a
separate audited live milestone is completed.**

## Always true for this repository

- [x] `TRADING_MODE` defaults to `paper`
- [x] `LiveTradingGate.allowed` is hard-blocked (`False`)
- [x] AI cannot submit orders
- [x] SafetyGuard blocks futures / leverage≠1 / withdrawals
- [x] Every order path uses `OrderGateway` → `RiskEngine`

## Paper production engine checklist

- [ ] `pytest -q` green
- [ ] `ruff check` / `ruff format --check` / `mypy app` green
- [ ] `alembic upgrade head` applied
- [ ] Shared DB pool used by cycle/scheduler paths
- [ ] Cycle lock fail-closed (`CYCLE_LOCK_FAIL_CLOSED=true`)
- [ ] Kill switch tested (activate → orders blocked)
- [ ] Reconciliation halt tested
- [ ] Restart hydration preserves cash/positions/fills
- [ ] Endurance replay green
- [ ] Scheduler disabled by default; enable only intentionally
- [ ] Admin token set; mutators fail closed without it
- [ ] CORS restricted to dashboard origins
- [ ] Secrets not committed; `.env` not in git
- [ ] Paper cycle smoke: BUY/HOLD + idempotent retry
- [ ] `/health` and `/ready` healthy
- [ ] Ops SSE `/ops/stream` delivers portfolio/recon heartbeats
- [ ] MarketDataHub status visible; advisory derivatives never enable futures
- [ ] Backtest metrics reviewed (Sharpe/Sortino/PF/CAGR/DD)
- [ ] Logging JSON operational
- [ ] Disaster recovery / DB backup plan documented

## Explicitly NOT ready (live)

- [ ] Live credentials vaulted + rotated
- [ ] Live approval token + `LIVE_STARTUP_ACK` process
- [ ] Live exchange connectivity soak
- [ ] Legal/risk acceptance for real capital

**Do not flip `ENABLE_LIVE_TRADING` or bypass the live gate.**
