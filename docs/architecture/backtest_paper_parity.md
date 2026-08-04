# Backtest / paper parity

## Shared domain pipeline

Where feasible, backtest and paper share:

- candle validation
- indicator calculation
- strategy signal generation (`app/strategies/*` via registry)
- order intent construction
- risk evaluation (`RiskEngine`)
- fee / slippage configuration from Settings
- portfolio accounting primitives in `PaperTradingEngine`

## Known differences (explicit)

| Area | Paper | Backtest |
|------|-------|----------|
| Clock | Wall-clock UTC + scheduler | Historical series only |
| Cycle locks | DB `cycle_locks` | Not used |
| Persistence | Journal + checkpoint + recon | In-memory report |
| Market data | Offline fixture or live public OHLCV | Caller-provided series |
| Kill switch / recon halt | Enforced on live session | Typically disabled in unit backtests unless injected |
| Partial fills | Deterministic paper rules | Often assumed full fill unless configured |

Backtests must not silently loosen risk limits relative to paper. When a backtest
constructs a `RiskEngine`, it should use the same Settings-derived limits.

## Regression stance

Integration/endurance tests replay deterministic candles through
`run_paper_trading_cycle` and assert accounting invariants. Prefer that path for
parity checks rather than a second divergent executor.
