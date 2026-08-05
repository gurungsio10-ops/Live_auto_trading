# System Architecture — Project Atlas (Paper V1)

## Purpose

Personal cryptocurrency **paper** trading platform with deterministic strategies, a mandatory risk gateway, durable state, and an operations dashboard.

## Canonical components

| Concern | Module |
|---------|--------|
| Settings | `app/core/config.py` |
| Safety / live gate | `app/core/safety.py`, `app/execution/live_gate.py` |
| Market data | `app/market_data/hub.py` → `facade.py` → providers |
| Strategies | `app/strategies/*` + `registry.py` |
| Risk | `app/risk/engine.py` |
| Order entry | `app/execution/gateway.py` |
| Paper ledger | `app/execution/paper/engine.py` |
| Cycle orchestration | `app/services/paper_cycle.py` |
| Session (UI cache) | `app/services/paper_session.py` |
| Persistence | `app/services/paper_persistence.py` + `app/repositories/*` |
| Journal | `app/journal/store.py` |
| Locks | `app/services/cycle_lock.py` |
| Reconciliation | `app/services/reconciliation.py` |
| Scheduler | `app/services/trading_scheduler.py` (disabled by default) |
| Invariants | `app/accounting/invariants.py` |
| APIs | `app/api/v1.py`, `app/api/dashboard.py` |
| Frontend | `frontend/` (BFF proxies; admin token server-side only) |

## Runtime flow

```text
Candles → validate → strategy → (advisory AI optional)
  → OrderGateway → RiskEngine → PaperTradingEngine
  → invariants → dual-write persistence + journal
  → /api/v1 + dashboard + /recovery
```

## Data durability

- Process memory is a cache for latency.
- Startup hydrates from DB; cycles dual-write checkpoint (0004) + first-class tables (0006).
- Persistence/recon failures pause trading (fail closed).

## Explicit non-goals

Live orders, futures, leverage >1x, withdrawals, autonomous AI execution.

See also: `paper_trading_flow.md`, `database_schema.md`, `risk_controls.md`, `docs/audits/consolidation_audit.md`.
