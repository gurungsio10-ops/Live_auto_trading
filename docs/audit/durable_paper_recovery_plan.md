# Durable Paper Trading & Recovery — Implementation Plan

**Branch:** `cursor/durable-paper-recovery-e3a2`  
**Constraint:** PAPER-ONLY. Live money hard-blocked.

## Audit summary

### Already durable
- Kill switch, trading_enabled, trading_paused (`system_state`)
- Portfolio checkpoint JSON + denormalized balances/positions/snapshots
- Cycle idempotency keys, cycle locks, recon halt, journal orders/fills (when attached)
- Audit events in `trade_journal`

### Still memory-only (gaps this phase closes)
- `_daily_start_equity`, fees aggregate, risk seen-keys / circuit breaker
- Strategy selection / params / running set
- First-class `PaperAccount` / `RiskState` / `StrategyState` / `ProcessedCycleKey` tables
- Startup recon exception swallowed → can leave trading open
- `clear_reconciliation_halt` does not clear DB
- Journal not auto-attached on bare `run_paper_trading_cycle`
- `StrategyRunORM` unwired

## Plan (reuse, no parallel ledger)
1. Alembic 0006 + ORM models — done
2. Thin repositories over persistence helpers — done
3. Dual-write account/risk/strategy/cycle-key tables + keep system_state keys — done
4. Hydrate all durable fields; bootstrap fail-closed on recon failure — done
5. Auto-attach JournalStore (non-memory DB); persist StrategyRunORM — done
6. Recovery status API + docs + tests — done

## Hot path (unchanged)
```
Candles → strategy → OrderGateway → RiskEngine → PaperTradingEngine
  → PaperSession + JournalStore + paper_persistence dual-write
```
