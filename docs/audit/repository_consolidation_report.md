# Repository Consolidation Report — Project Atlas

**Date:** 2026-08-04  
**Working branch:** `cursor/paper-consolidation-e3a2` (from `cursor/production-readiness-e3a2`)  
**Constraint:** PAPER-ONLY. Live money remains hard-blocked.

## 1. Architecture map

```text
Candles (offline | live public CCXT)
  → validate/normalize
  → strategy (registry)
  → OrderGateway → RiskEngine
  → PaperTradingEngine (fills, WAC, fees)
  → PaperSession + JournalStore + paper_persistence
  → FastAPI (dashboard roots + /api/v1)
  → Next.js BFF → Dashboard
```

| Package | Responsibility | SSOT |
|---------|----------------|------|
| `app/core/config.py` | Settings | Yes |
| `app/core/runtime_mode.py` | Runtime mode derivation | Yes |
| `app/core/safety.py` | Live/futures/leverage/withdraw blocks | Yes |
| `app/risk/engine.py` | Pre-trade risk | Yes |
| `app/execution/gateway.py` | Risk-first entry | Yes |
| `app/execution/paper/engine.py` | Paper fills | Yes |
| `app/services/paper_cycle.py` | Canonical cycle | Yes |
| `app/services/trading_orchestrator.py` | Candle→fill orchestration | Yes |
| `app/services/paper_session.py` | Runtime + dashboard state | Yes |
| `app/services/paper_persistence.py` | Durable checkpoint | Yes |
| `app/journal/store.py` | Ledger ORMs + writes | Yes |
| `app/services/trading_scheduler.py` | Continuous cycles | Yes |
| `app/services/reconciliation.py` | Ledger vs materialised | Yes |
| `app/api/dashboard.py` | UI HTTP contract | Yes |
| `app/api/v1.py` | Automation API | Yes |
| `app/api/mvp.py` | Checklist aliases (thin) | Keep as shim |
| `app/api/routes.py` | Legacy AI/live-gate | Keep AI only |

## 2. Open PR inventory

| PR | Branch | Disposition |
|----|--------|-------------|
| #23 | `cursor/production-readiness-e3a2` | **Base** — retain |
| #22 | `feature/paper-trading-mvp` | Superseded by #23 |
| #21 | `cursor/paper-trading-e2e-e3a2` | Superseded by #23 |
| #20 | `cursor/binance-spot-testnet-pipeline-e3a2` | Defer (testnet soak; out of paper milestone) |
| #18 | `cursor/live-gate-hardening-dc9d` | Cherry-pick ideas only; keep hard-block |
| #3–#17 | phase verification ladder | Close as superseded |

## 3. Duplicate implementations (resolved on this branch)

| Subsystem | Conflict | Resolution |
|-----------|----------|------------|
| `trading_enabled` | `mvp._TRADING_ENABLED` vs Settings | **PaperSession.trading_enabled** + DB persist |
| Kill switch | 4 HTTP surfaces | All call `PaperSession.set_kill_switch` |
| MarketDataService | facade vs service | Facade for cycles; persist service stays for sync tests |
| PaperBroker vs Engine | Parallel | Hot path = Engine+Gateway; Broker = thin wrapper |
| Health models | monitoring vs domain | Root `/health`/`/ready` authoritative |
| Strategy runners | session tick vs cycle | Cycle is canonical; session tick delegates |

## 4. Database entities (current + planned)

**Alembic 0001–0004:** symbols, candles, signals, risk_decisions, orders, fills, system_events, users, strategy_runs, balances, positions, portfolio_snapshots, trade_journal, system_state.

**0005 (this branch):** cycle_locks, scheduler_runs, reconciliation_reports, paper_accounts.

## 5. Technical debt ranking

### Critical
1. Process-memory paper state that reset on restart (partially fixed; completing hydrate + locks)
2. Multiple trading-enable control planes
3. Cycles without distributed/DB lock

### High
4. Scheduler imported `app.api.mvp`
5. Journal not attached on all HTTP cycles
6. Reconciliation not mandatory after every cycle
7. API surface sprawl

### Medium
8. Dual MarketDataService names
9. Docs triplication
10. Redis unused for locks (DB locks used instead)

### Low
11. Unwired WS/futures/news→risk
12. AGENTS.md strategy list drift

## 6. Retain / modify / remove

| Action | Target |
|--------|--------|
| Retain | RiskEngine, OrderGateway, PaperTradingEngine, paper_cycle, PaperSession, JournalStore |
| Modify | Scheduler (decouple), mvp (shim to session), hydrate, cycle locks |
| Defer merge | PR #20 testnet pipeline |
| Do not remove yet | `routes.py` AI endpoints, `broker.py` (tests), persist MD service |
