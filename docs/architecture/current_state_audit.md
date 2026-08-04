# Project Atlas — Current State Audit (Paper V1)

**Date:** 2026-08-04  
**Branch:** `cursor/release-paper-v1-consolidated-e3a2` (from PR #26 tip)  
**Scope:** Authoritative production-quality **PAPER** trading platform

This document replaces older draft audits that described pre-consolidation architecture.

---

## Runtime mode

| Mode | Status |
|------|--------|
| PAPER | Supported (default) |
| TESTNET observation | Market data only; no live money |
| LIVE | Hard-blocked |

## Authoritative modules

| Subsystem | Path |
|-----------|------|
| Config / safety | `app/core/config.py`, `safety.py`, `runtime_mode.py` |
| Risk | `app/risk/engine.py` (mandatory via `OrderGateway`) |
| Paper execution | `app/execution/paper/engine.py` |
| Order gateway | `app/execution/gateway.py` |
| Paper session | `app/services/paper_session.py` |
| Cycle | `app/services/paper_cycle.py` |
| Orchestrator | `app/services/trading_orchestrator.py` |
| Persistence | `app/services/paper_persistence.py` + `app/repositories/*` |
| Journal | `app/journal/store.py` |
| Reconciliation | `app/services/reconciliation.py` |
| Scheduler | `app/services/trading_scheduler.py` (off by default) |
| Cycle locks | `app/services/cycle_lock.py` |
| Accounting invariants | `app/accounting/invariants.py` |
| Soak harness | `app/services/paper_soak.py` |
| Market data | `app/market_data/hub.py` → facade/providers |
| APIs | `app/api/v1.py`, `dashboard.py` (MVP aliases in `mvp.py`) |
| Frontend | `frontend/` including `/recovery` |

## Fully implemented (paper)

- Offline + optional public OHLCV
- Strategies: `ema_crossover`, `ema_rsi`, `ema_trend`, `rsi_mean_reversion`, `breakout`
- Risk engine with durable `risk_state`
- Paper broker realism (fees, slippage, partial fills, stop/TP, expiry)
- Dual-write durable account state (Alembic `0006_paper_durable`)
- Fail-closed bootstrap + cycle persist
- Processed-cycle idempotency
- Reconciliation halt + admin clear
- Recovery status API + dashboard Recovery panel
- Ops SSE (`/ops/stream`)
- Soak harness + accounting invariants
- CI gates including ≥85% app coverage

## Explicitly not implemented

- Live money order placement
- Futures / margin / leverage >1x
- Withdrawals / deposits / wallet signing
- Autonomous AI execution

## Competing surfaces (aliases, not forks)

HTTP aliases under `/api/*` (MVP) and `/api/v1/*` share the same `PaperSession` source of truth. Do not treat them as separate ledgers.

## Obsolete / secondary

| Path | Status |
|------|--------|
| `app/market_data/service.py` | Deprecated twin of facade (tests/legacy) |
| Older phase audit % claims | Superseded by `docs/audit/paper_v1_final_verification.md` |

## Honest completion

- Paper platform: ~92%
- Live platform: 0% enabled
