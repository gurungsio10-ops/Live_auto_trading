# System overview — Project Atlas (paper)

## Purpose

Project Atlas is a personal **paper-trading** cryptocurrency platform. Live money
execution remains hard-blocked.

## Hot path (authoritative)

```text
Candles → validation → strategy → OrderGateway → RiskEngine
  → PaperTradingEngine → PaperSession + JournalStore + paper_persistence
  → FastAPI → Next.js BFF → Dashboard
```

| Concern | Source of truth |
|---------|-----------------|
| Settings | `app/core/config.py` |
| Trading mode / runtime | `app/core/runtime_mode.py` |
| Risk | `app/risk/engine.py` |
| Paper fills | `app/execution/paper/engine.py` |
| Cycle orchestration | `app/services/paper_cycle.py` |
| Runtime dashboard state | `app/services/paper_session.py` |
| Durable checkpoint | `app/services/paper_persistence.py` |
| Cycle locks / scheduler runs | `app/services/cycle_lock.py` |
| Reconciliation | `app/services/reconciliation.py` |
| Scheduler | `app/services/trading_scheduler.py` |

See also: `docs/architecture/paper_trading_flow.md`, `docs/architecture/risk_controls.md`.
