# Project Atlas — Architecture Roadmap

Phases must be completed in order. Do not start a phase whose prerequisites
are not marked **done**.

## Live trading gating checklist (Phase 14)

All nine conditions must be true simultaneously for a live order to submit:

1. `TRADING_MODE == "live"`
2. `LIVE_TRADING_ENABLED == true`
3. `KILL_SWITCH_ENABLED == false`
4. Valid exchange credentials present
5. Risk engine healthy
6. Market data healthy
7. Database healthy
8. Reconciliation healthy
9. Valid manual live-approval token

## Phase status

| Phase | Name | Status | Prerequisites |
|------:|------|--------|---------------|
| 1 | Foundation (config, security, domain models, API skeleton) | **done** | — |
| 2 | Historical Market Data | **done** | Phase 1 |
| 3 | Indicators | **done** | Phase 2 |
| 4 | Strategy Framework | **done** | Phase 3 |
| 5 | Backtesting Engine | **done** | Phase 4 |
| 6 | Risk Engine | **done** | Phase 5 |
| 7 | Paper Trading Engine | pending | Phase 6 |
| 8 | Live Market Data (WebSocket) | pending | Phase 7 |
| 9 | Portfolio and Journal | pending | Phase 8 |
| 10 | Monitoring | pending | Phase 9 |
| 11 | Dashboard (Next.js) | pending | Phase 10 |
| 12 | AI Analysis Layer (advisory only) | pending | Phase 11 |
| 13 | News Sentiment | pending | Phase 12 |
| 13.5 | Testnet Execution | pending | Phase 13 |
| 14 | Live Trading Preparation | pending | Phase 13.5 |
| 15 | Futures and Leverage | pending | Phase 14 stable |

## Notes

- `TRADING_MODE` defaults to `paper` and must never be changed in code defaults.
- AI (`app/ai/`) is advisory only and must never call order submission.
- Every order path must pass through `app/risk/engine.py`.
