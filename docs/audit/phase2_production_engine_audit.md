# Phase 2 — Production Trading Engine Audit

**Date:** 2026-08-04  
**Branch base:** `cursor/paper-consolidation-e3a2` (PR #24)  
**Working branch:** `cursor/production-trading-engine-e3a2`  
**Hard constraint:** PAPER-ONLY. Live money remains hard-blocked. Leverage/futures/withdrawals remain blocked. AI remains advisory.

## 1. Current architecture

```text
Candles (offline | live public CCXT)
  → validate/normalize
  → strategy (registry)
  → OrderGateway → RiskEngine
  → PaperTradingEngine
  → PaperSession + JournalStore + paper_persistence
  → FastAPI → Next.js BFF → Dashboard
```

Authoritative SSOTs are listed in `docs/architecture/system_overview.md` and
`docs/audit/repository_consolidation_report.md`.

## 2. Folder structure

| Path | Role |
|------|------|
| `app/core` | Config, safety, logging, runtime mode |
| `app/market_data` | Providers, facade, validators, WS client |
| `app/strategies` | Interchangeable signal strategies |
| `app/risk` | Pre-trade risk engine |
| `app/execution` | Gateway, paper engine, live gate, testnet stub |
| `app/services` | Cycle, session, scheduler, recon, locks |
| `app/journal` | Durable ledger ORMs |
| `app/portfolio` | Thin helper (to be expanded as PortfolioManager) |
| `app/ai`, `app/news` | Advisory only |
| `app/backtesting` | Offline backtest |
| `app/api` | dashboard / v1 / mvp / routes / auth |
| `frontend/` | Ops dashboard |
| `alembic/` | Migrations 0001–0005 |
| `tests/` | Unit + integration |

## 3–13. Component inventory (summary)

| Area | Status | Notes |
|------|--------|-------|
| Market data | Partial | REST OHLCV via CCXT; WS client exists but unwired |
| Portfolio | Partial | PaperSession is runtime SSOT; `PortfolioService` thin |
| Execution | Strong (paper) | Market fills via gateway; limit/stop partial |
| Risk | Strong | Fail-closed; kill switch; recon halt |
| AI | Advisory | No execution imports |
| Strategies | Present | Registry + config params |
| Paper trading | Strong | Fees, slippage, WAC, idempotency, locks |
| Backtesting | Present | Needs richer metrics pack |
| Dashboard | Present | Polling; needs SSE/realtime |
| Auth | Present | Session + admin token |
| Logging | Present | structlog JSON; JSON `/metrics` |
| Config | Present | pydantic-settings |
| Testing | Strong | 197 tests, ~78% coverage |

## Gaps / debt (ranked)

### Critical
1. Per-call `create_engine()` churn (no shared pool usage on hot path)
2. Cycle lock `unavailable` soft-path can fall back to memory-only uniqueness
3. Docs sprawl / stale phase reports vs PR #24 truth

### High
4. Scheduler coverage low; multi-symbol sequential workers missing
5. Dual strategy tick paths (synthetic session tick vs canonical cycle)
6. API surface sprawl
7. No SSE/realtime ops updates

### Medium
8. Dual MarketDataService naming
9. Redis unused
10. CORS not configured on FastAPI
11. Funding/OI advisory feeds absent

### Low
12. Unwired futures math / WS / news→risk (keep trading blocked)
13. Frontend mock residue / sidebar phase label

## Open PR disposition

| PR | Disposition |
|----|-------------|
| #24 | Base / merge candidate |
| #21–#23 | Superseded by #24 |
| #20 | Defer (testnet soak) |
| #18 | Cherry-pick ideas only |
| #3–#17 | Close as superseded |

## Explicit non-goals (this phase)

- Enabling `TRADING_MODE=live` or bypassing `LiveTradingGate`
- Leverage, futures order placement, withdrawals, wallet signing
- AI modules that submit orders
- Parallel rewrites of RiskEngine / paper_cycle / PaperSession / OrderGateway
