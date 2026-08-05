# Consolidation Audit — Project Atlas Paper Platform

**Date:** 2026-08-04  
**Working branch:** `cursor/release-paper-v1-consolidated-e3a2` (PR #27)  
**Constraint:** PAPER ONLY. Live money, futures, leverage >1x, withdrawals, deposits, copy trading, and autonomous AI execution remain disabled.

## Lineage (verified)

```text
main 88c312e
  └─ #21 ⊂ #22 ⊂ #23 ⊂ #24 ⊂ #25 ⊂ #26 ⊂ #27 (tip)
```

Path-set uniqueness: `|⋃(#21…#26) − #27| = 0`. No stranded unique files on earlier tips.

**PR #25 is the leading candidate *feature* tip before durable recovery; PR #26 adds Alembic 0006 + restart-safe state; PR #27 is the release consolidation built on #26.** Evidence does **not** support merging #25 alone — it would regress durability.

## Comparison matrix

| Area | Main implementation | Candidate (#25) | Better/missing earlier | Chosen canonical | Reason | Tests | Migration impact | Compatibility risk |
|------|---------------------|-----------------|------------------------|------------------|--------|-------|------------------|--------------------|
| Config | pydantic Settings | Same lineage | — | `app/core/config.py` | Single Settings model | `test_config_security` | none | low |
| Market data | Binance provider | Hub + facade | #25 hub | `market_data/hub.py` → facade | Unified heartbeat/status | `test_binance_provider`, hub tests | none | medium (service.py twin deprecated) |
| Candle validation | validators | Same | — | `validators/candles.py` + orchestrator rejects | Closed/ordered/OHLC | `test_candle_validators` | none | low |
| Strategy registry | ema_trend | + ema_crossover/rsi/breakout/ema_rsi | #22+ | `strategies/registry.py` | One registry | strategy unit tests | none | low |
| Strategy execution | orchestrator | paper_cycle + orch | #24 cycle façade | `paper_cycle.run_paper_trading_cycle` | Single cycle entry | cycle/idempotency/concurrent | none | **dashboard tick now delegates here** |
| Advisory AI | routes score | Same | — | `app/ai/*` advisory only | Never submits orders | AI unit tests | none | low |
| Risk | RiskEngine | Same + durable risk_state (#26) | #26 | `risk/engine.py` via OrderGateway | Mandatory gate | `test_risk_engine` | 0006 | low |
| Cycle orchestration | TradingOrchestrator | paper_cycle wrapper | #24 | `paper_cycle` | API + scheduler + session tick | integration cycle tests | 0005 locks | low |
| Paper broker | PaperTradingEngine | + PaperBroker wrapper | — | Engine + Gateway | Broker is thin SafetyGuard wrap | broker/mvp tests | none | low |
| Portfolio accounting | PaperState WAC | + PortfolioManager view | #25 manager | Engine ledger + `accounting/invariants` | One ledger | accounting table tests | 0006 | medium (reserved_capital column unused) |
| Persistence | 0004 checkpoint | dual-write 0006 | **#26 required** | `paper_persistence` + repos | Restart-safe | durable recovery tests | **0006** | medium if skip 0006 |
| Cycle locking | none | 0005 locks | #24 | `cycle_lock.py` | Fail-closed | lock + concurrent tests | 0005 | low |
| Idempotency | engine keys | + processed_cycle_keys | #26 | cycle keys + order idempotency | Duplicate-safe | concurrent cycles | 0006 | low |
| Reconciliation | none | recon service | #23/#24 | `reconciliation.py` | Fail-closed halt | recon tests | 0005 reports | low |
| Scheduler | none | trading_scheduler | #23 | `trading_scheduler.py` | Off by default; uses paper_cycle | scheduler guards | 0005 runs | low |
| Kill switch | session flag | + kill_switch_events | #26 | PaperSession + 0006 events | Durable | API/session tests | 0006 | low |
| Journal | JournalStore | auto-attach in cycle | — | `journal/store.py` | Durable fills/orders | journal tests | 0002 | low |
| Health/ready | main probes | + mvp/v1 aliases | — | `main.py` `/health` `/ready` | DB + recon fail-closed | main ops tests | none | medium (alias sprawl) |
| Dashboard SSE | none | `/ops/stream` | #25 | `main.py` ops stream | Ops console | manual/UI | none | low |
| Recovery UI | none | — | **#27** | `/recovery` + BFF | Ops SoT panel | recovery API tests | none | low |
| Soak harness | none | — | **#27** | `paper_soak` CLI | Deterministic endurance | soak short test | none | low |

## Decision table (required format)

| Area | Main implementation | Candidate implementation | Decision | Risk | Required action |
|------|---------------------|--------------------------|----------|------|-----------------|
| Merge tip | Phase-16 paper slice | #25 engine / #26 durable / #27 release | **Retain #27** | Low if squash | MERGE #27; close #21–#26 |
| HTTP routers | dashboard + routes | + mvp + v1 | **Canonical: dashboard + v1**; mvp deprecated alias | Medium confusion | Document; no new mvp logic |
| Cycle path | orchestrator CLI | paper_cycle | **paper_cycle only** | Medium if tick bypass remains | Session tick delegated (done) |
| Paper SoT | process memory | dual-write 0006 | **DB durable + memory cache** | High if skip hydrate | Keep fail-closed persist |
| Market data service.py | present | hub/facade | **Deprecate service.py** | Low | Coverage omit; docs |
| Portfolio twins | service.py | manager.py | **Engine ledger; manager view** | Low | Keep manager as view |
| Reserved cash | absent | column default 0 | **Document limitation** | Medium for resting limits | Next milestone |
| Docs sprawl | many audits | overlapping | **docs/audits + architecture current** | Low | Mark stale docs |

## Duplicate / obsolete findings

- **Duplicate routers:** `mvp.py` (deprecated), `routes.py` (legacy AI/controls), `dashboard.py`, `v1.py`
- **Competing cycle:** CLI `paper-run` still constructs orchestrator directly for streaming offline feed (acceptable streaming tool; one-shot ops use paper_cycle)
- **Module mutable state:** session/cycle/scheduler/recon singletons — hydrated/persisted where durable
- **Hidden in-memory:** runtime cache OK; durable SoT is DB
- **Stale docs:** `docs/PRODUCTION_STATUS.md`, phase16 audits, uppercase CURRENT_STATE copies
- **Reserved capital:** runtime `PaperState.reserved_cash` dual-written to `paper_accounts.reserved_capital` + checkpoint; reserve on BUY accept, release exactly once on fill/cancel/reject/expire

## Authoritative runtime flow

```text
Market-data / offline fixtures
  → candle validation
  → strategy evaluation
  → advisory enrichment (optional, non-ordering)
  → OrderGateway → RiskEngine
  → PaperTradingEngine fill
  → portfolio accounting + invariants
  → paper_persistence dual-write + journal
  → metrics / recovery APIs
  → dashboard (+ /recovery)
```

## Assumptions

1. Squash-merge of #27 into `main` is preferred.
2. MVP `/api/*` aliases remain until external checklist consumers migrate to `/api/v1`.
3. Live/testnet execution stays out of scope for this consolidation.
