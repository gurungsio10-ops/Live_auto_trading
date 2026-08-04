# Paper trading recovery runbook

## Startup sequence

```text
DB available?
  ├─ create missing tables (dev) / alembic upgrade head (prod)
  ├─ hydrate PaperSession
  │    ├─ kill_switch / trading_enabled / trading_paused
  │    ├─ reconciliation_halt → risk + process halt flags
  │    ├─ paper_checkpoint (+ paper_accounts fallback)
  │    ├─ risk_state / strategy_state
  │    ├─ journal orders/fills (or checkpoint fallback)
  │    └─ processed cycle keys
  ├─ run_paper_reconciliation(persist=True)
  │    ├─ healthy → trading allowed
  │    └─ unhealthy / exception → halt + pause (fail closed)
  └─ refuse new orders while halted / kill switch / unhealthy deps
```

## Recovery status API + dashboard

- `GET /api/v1/recovery/status` — durable recovery snapshot (backend SoT)
- Dashboard **Recovery** page: `frontend/app/recovery` via BFF `GET /api/recovery/status`
- Panel fields include: runtime mode, trading enabled/paused, kill switch, recon halt, last cycle, last hydration, persistence/DB/scheduler status, stale MD, open orders/positions, equity, latest recon
- `GET /api/recovery/status` — MVP alias
- `GET /api/reconciliation/status` — last recon result
- `POST /api/reconciliation/run` — admin, re-run checks
- `POST /api/v1/reconciliation/clear-halt` — admin, clear durable halt after fix
- Dashboard clear-halt BFF requires confirm `CLEAR_RECONCILIATION_HALT` and server-side `ADMIN_API_TOKEN` (never browser-exposed)

## On reconciliation halt

1. New orders blocked (`reconciliation_healthy=false`)
2. Inspect mismatches via recon status / report table
3. Fix root cause (do **not** silently rewrite cash)
4. `POST /reconciliation/run` until healthy
5. `POST /reconciliation/clear-halt` if a prior halt flag remains
6. Confirm `GET /recovery/status` shows healthy

## Restart safety invariants

After stop/start, these must match pre-restart durable state:

- cash, positions, WAC entry, realised/unrealised PnL
- open + completed orders, fills
- daily start equity, peak equity, consecutive losses
- kill switch, recon halt, risk seen-keys / circuit breaker
- strategy selection / params
- processed cycle keys (no duplicate orders for same candle)

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Trading blocked after restart | `GET /recovery/status` — halt / kill switch / DB unhealthy |
| Duplicate orders | cycle keys + order `idempotency_key` unique + risk seen-keys |
| Cash drift | recon mismatches; fill ledger completeness |
| Strategy reset | `strategy_state` row for `paper-default` |
| Empty fills after restart | journal attached? checkpoint `fills`/`orders` present? |
