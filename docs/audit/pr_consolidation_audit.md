# PR Consolidation Audit — Paper V1 Release

**Date:** 2026-08-04  
**Authoritative tip:** `cursor/durable-paper-recovery-e3a2` @ `d1a3b69` (PR #26)  
**Release branch:** `cursor/release-paper-v1-consolidated-e3a2`  
*(Named per cloud-agent branch policy; semantically the Paper V1 consolidated release.)*  
**Constraint:** PAPER ONLY. No live money, futures, leverage >1x, withdrawals, or autonomous AI execution.

## Lineage map

```
main (88c312e)
  └─ #21 paper-trading-e2e
       └─ #22 paper-trading-mvp
            └─ #23 production-readiness
                 └─ #24 paper-consolidation (+ Alembic 0005)
                      └─ #25 production-trading-engine
                           └─ #26 durable-paper-recovery (+ Alembic 0006)  ← preferred base
                                └─ cursor/release-paper-v1-consolidated-e3a2  ← THIS RELEASE
```

Verified: `#21 ⊂ #22 ⊂ #23 ⊂ #24 ⊂ #25 ⊂ #26`. Path-set `|⋃(#21…#25) − #26| = 0`.

## Examined PRs

| PR | Branch | Disposition | Rationale |
|----|--------|-------------|-----------|
| #21 | `cursor/paper-trading-e2e-e3a2` | **superseded / close after merge** | Ancestor of #26; no unique paths |
| #22 | `feature/paper-trading-mvp` | **superseded / close after merge** | MVP surface retained in #26 tip |
| #23 | `cursor/production-readiness-e3a2` | **superseded / close after merge** | Scheduler/recon retained in #26 |
| #24 | `cursor/paper-consolidation-e3a2` | **superseded / close after merge** | 0005 + cycle locks retained |
| #25 | `cursor/production-trading-engine-e3a2` | **superseded / close after merge** | Hub/pool/SSE retained |
| #26 | `cursor/durable-paper-recovery-e3a2` | **retain (base)** | Full durable recovery; CI green |
| #20 | `cursor/binance-spot-testnet-pipeline-e3a2` | **close after merge (out of scope)** | Testnet pipeline; not paper-v1 |
| #18 | `cursor/live-gate-hardening-dc9d` | **partially retain (ideas only)** | Live-gate hardening already reflected; do not merge as branch |
| #3–#17 | phase verification branches | **close after merge** | Historical verification; superseded |

## Authoritative subsystem map

| Subsystem | Authority |
|-----------|-----------|
| Runtime config | `app/core/config.py` |
| Paper session | `app/services/paper_session.py` |
| Risk | `app/risk/engine.py` via `OrderGateway` |
| Paper execution | `app/execution/paper/engine.py` |
| Cycle | `app/services/paper_cycle.py` |
| Orchestrator | `app/services/trading_orchestrator.py` |
| Persistence | `app/services/paper_persistence.py` + `app/repositories/*` |
| Journal | `app/journal/store.py` |
| Scheduler | `app/services/trading_scheduler.py` |
| Cycle locks | `app/services/cycle_lock.py` |
| Reconciliation | `app/services/reconciliation.py` |
| Market data | `app/market_data/hub.py` → facade |
| Portfolio wrap | `app/portfolio/manager.py` (dashboard session remains SoT) |
| Ops API | `app/api/v1.py` + `app/api/dashboard.py` |
| MVP aliases | `app/api/mvp.py` (keep; documented aliases) |
| Legacy routes | `app/api/routes.py` (AI advisory + legacy controls) |

## Competing surfaces (kept intentionally)

Multiple HTTP paths for kill-switch / portfolio / recovery remain as **aliases** of the same `PaperSession` methods. They are not parallel ledgers. Release docs designate:

- Dashboard UI → `app/api/dashboard.py`
- Automation / versioned → `/api/v1/*`
- Checklist / ops aliases → `/api/*` (mvp)

## Obsolete / secondary

| Path | Status |
|------|--------|
| `app/market_data/service.py` | Secondary twin of facade; tests only — mark deprecated in docs |
| `docs/PRODUCTION_STATUS.md` | Stale % claims — superseded by release verification doc |
| Local `*.db` artifacts | Not source; gitignored / ignore in release |

## Decision

Build release from **PR #26 tip**. Do not cherry-pick older tips. Close #21–#25 (and phase PRs) after release merge.
