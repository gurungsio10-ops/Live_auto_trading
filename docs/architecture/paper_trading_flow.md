# Paper trading flow

End-to-end deterministic paper path for BTC/USDT (1m):

```text
Market data (public / offline fixture)
  → candle validation (closed, ordered, OHLC-sane)
  → strategy evaluation (EMA crossover 9/21)
  → trade signal (BUY / SELL / HOLD)
  → order intent (if actionable)
  → central risk engine (mandatory)
  → approved intent
  → paper broker (fees + slippage)
  → fill
  → portfolio update (weighted-average cost)
  → trade journal / snapshots
  → API (/api/v1) + dashboard
```

## Entry points

| Entry | Module | Notes |
|-------|--------|-------|
| `run_paper_trading_cycle(...)` | `app/services/paper_cycle.py` | Single-cycle façade (API + tests) |
| `TradingOrchestrator.process_candle` | `app/services/trading_orchestrator.py` | Event-driven core |
| CLI `python -m app.cli paper-run` | `app/cli.py` | Streaming offline/public feed |
| CLI `python -m app.cli paper-soak` | `app/services/paper_soak.py` | Deterministic endurance harness |
| Dashboard “Run one paper cycle” | Next BFF → `/api/v1/paper/cycle/run` | Shares hydrated paper session |
| Recovery panel | `frontend/app/recovery` → `/api/v1/recovery/status` | Ops SoT view |

Post-cycle, `app/accounting/invariants.py` checks
`cash + reserved_cash + marked_position_value = equity` (fail-closed on critical violations).

## Reserved capital (buying power)

- `PaperState.cash` = **available** quote balance (unreserved).
- `PaperState.reserved_cash` = capital locked for open **BUY** orders (persisted as `paper_accounts.reserved_capital`).
- On BUY accept: reserve `qty * reference_price` (limit/trigger/mark) from available → reserved.
- On fill: release proportional reservation back to available, then debit actual fill cost + fee.
- On cancel / expire / reject / fail: release remaining reservation **exactly once** (idempotent).
- RiskEngine buying-power checks use available `cash_balance` only (never weakens OrderGateway).

## Idempotency

- Orders: `idempotency_key` unique in paper engine + risk seen-set (persisted).
- Cycles: `(symbol, strategy_version, timeframe, candle_open_time)` at most once — process set + `system_state` + `processed_cycle_keys`.
- Strategy fingerprints prevent duplicate action on identical inputs.
- Restart hydrate restores orders/fills/idempotency from journal or checkpoint.

## Durability

After each accepted cycle the runtime dual-writes `paper_accounts`, `risk_state`, `strategy_state`, equity snapshots, and the legacy checkpoint. See `docs/operations/recovery_runbook.md`.

## Cost basis

Weighted average cost (WAC) on buys; realized PnL on sells against average entry. Documented in paper engine.

## Safety

- `TRADING_MODE=paper` by default.
- Live execution raises `LiveTradingDisabledError`.
- Kill switch rejects new orders; read APIs remain available.
- AI modules never submit orders.

See also: `docs/architecture/paper_trading_data_flow.md`.
