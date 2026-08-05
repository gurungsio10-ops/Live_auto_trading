# Phase 2 implementation roadmap

**Constraint:** PAPER-ONLY. Live remains hard-blocked.

## Milestone plan

| ID | Milestone | Status |
|----|-----------|--------|
| M0 | Audit + roadmap (this doc + phase2 audit) | Done |
| M1 | Shared async DB pool; fail-closed cycle locks | Done |
| M2 | Unified MarketDataHub (REST + heartbeat + advisory funding/OI) | Done |
| M3 | PortfolioManager (period PnL, exposure, equity curve sync) | Done |
| M4 | Paper execution lifecycle hardening (`cancel`) | Done (partial — trailing/scale later) |
| M5 | Advisory AI decision modules (score/explain/RR) — no orders | Done |
| M6 | Backtest metrics pack (+ CAGR / average trade) | Done |
| M7 | Ops SSE `/ops/stream` | Done |
| M8 | CORS + production checklist + tests | Done |

## Design rules

1. Extend existing SSOTs; do not fork parallel engines.
2. Every order still through `OrderGateway` → `RiskEngine`.
3. Futures/leverage/margin trading remain blocked by `SafetyGuard`.
4. Funding / OI / liquidation streams are **read-only advisory** market data.
5. “Sync with exchange” for personal production means: paper/testnet state
   reconstructed from durable journal + public MD marks — not live money sync.
6. Ship tests with each milestone.

## Definition of done for Phase 2 (paper production engine)

- Shared DB pool used by cycle/scheduler/recon paths
- Lock unavailable → cycle rejected (fail closed)
- MarketDataHub exposes status, heartbeat, advisory derivatives MD
- PortfolioManager reports daily/weekly/monthly PnL from paper state
- SSE stream for ops dashboard
- Backtest metrics expanded
- Production readiness checklist documented; live still disabled
- Quality gates green
