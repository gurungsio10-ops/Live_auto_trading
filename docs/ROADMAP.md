# Project Atlas — Roadmap

## Current verified state (2026-08-04)

| Area | Status |
|------|--------|
| Paper cycle (signal → risk → fill → dashboard) | **done** |
| Runtime modes BACKTEST/PAPER/TESTNET/LIVE | **done** (LIVE hard-blocked) |
| Kill switch + portfolio restart hydrate | **done** |
| Cycle idempotency across restart | **done** |
| Frontend fills + runtime badge | **done** |
| Spot Testnet pipeline | separate branch / PR |
| Live money trading | **blocked** |
| Futures / leverage / HFT / copy trading | **out of scope** |

## Near-term milestones

1. Continuous paper runtime (candle poll loop) with pause/start APIs
2. Full ORM hydrate for orders/fills/signals on startup
3. Admin token on all dashboard mutators
4. CI coverage ≥90% on `app.risk` + `app.execution`
5. Optional Spot Testnet soak (keys required; not live money)

## Explicit non-goals (this phase)

- Real-money LIVE execution
- Futures, leverage, autonomous self-learning order agents
- Optimising strategies for fixture profitability
