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
| Dashboard “Run one paper cycle” | Next BFF → `/api/v1/paper/cycle/run` | Shares in-memory paper session |

## Idempotency

- Orders: `idempotency_key` unique in paper engine + risk seen-set.
- Cycles: `(symbol, strategy_version, timeframe, candle_open_time)` processed at most once per process.
- Strategy fingerprints prevent duplicate action on identical inputs.

## Cost basis

Weighted average cost (WAC) on buys; realized PnL on sells against average entry. Documented in paper engine.

## Safety

- `TRADING_MODE=paper` by default.
- Live execution raises `LiveTradingDisabledError`.
- Kill switch rejects new orders; read APIs remain available.
- AI modules never submit orders.

See also: `docs/architecture/paper_trading_data_flow.md`.
