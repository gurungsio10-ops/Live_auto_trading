# PR Consolidation Audit — Project Atlas

**Audit date:** 2026-08-05 (UTC, release-engineer pass)  
**Authoritative release candidate:** PR **#34** / branch `release/atlas-paper-v1`  
**Tip SHA (pre-this-commit):** `f4ed67bbb955906d9f3916a0404ffff4e5570304`  
**Base tip included:** PR #28 `cursor/codespaces-auto-start-e3a2` (`2ed644a`)  
**Base:** `origin/main` (`88c312e`)

## Executive summary

Verified via `git fetch`, `git merge-base --is-ancestor`, `gh pr view 34`, code inspection, and local quality gates:

1. **Linear paper lineage:** `#21 ⊂ #22 ⊂ #23 ⊂ #24 ⊂ #25 ⊂ #26 ⊂ #27 ⊂ #28 ⊂ release/atlas-paper-v1`
2. **PR #23 is an ancestor** of the tip (`29107fed…` is ancestor of HEAD). Scheduler / hydrate / reconcile / compose from #23 are included.
3. **PR #34** is the sole merge vehicle for paper-v1. Do **not** merge #21–#33 individually.
4. **PR #20** (Binance Spot Testnet) is **not** an ancestor — keep open as isolated testnet candidate.
5. **PR #33** (control-centre) is **not** an ancestor — park and rebase onto post-merge `main` later; do not merge now.

---

## Lineage diagram

```text
main (88c312e)
 └── #21 paper-trading-e2e
      └── #22 feature/paper-trading-mvp
           └── #23 production-readiness   ← INCLUDED (ancestor)
                └── #24 paper-consolidation
                     └── #25 production-trading-engine
                          └── #26 durable-paper-recovery
                               └── #27 release-paper-v1-consolidated
                                    └── #28 codespaces-auto-start  ← tip base (2ed644a)
                                         └── release/atlas-paper-v1  ← PR #34

Parallel / divergent (do not replace tip):
  #20 testnet pipeline (separate — KEEP)
  #29 / #30 premium mobile UI (main-fork UI — CLOSE)
  #31 durable-paper-platform (diverged + backend CI red — CLOSE)
  #32 atlas-mobile-ops-ui (UI polish on #31 line — CLOSE)
  #33 atlas-control-centre (control-centre on #32 line — PARK/REBASE later)

Obsolete conflicting verification:
  #3 … #18 (phase*-verification-dc9d, live-gate-hardening)
```

---

## Ancestor evidence (merge-base)

| Branch / PR tip | SHA | `merge-base --is-ancestor … HEAD` |
|-----------------|-----|-----------------------------------|
| #28 `cursor/codespaces-auto-start-e3a2` | `2ed644a5210ac04eb293443345473441106209b5` | **YES** |
| #27 `cursor/release-paper-v1-consolidated-e3a2` | `18e1cb271e691f4a4b4ccd3b5648be9cefa1e689` | **YES** |
| #23 `cursor/production-readiness-e3a2` | `29107fed57921cad63afcbbf995cbb96ec4f3560` | **YES** |
| #20 `cursor/binance-spot-testnet-pipeline-e3a2` | `a2144a51354194ae3517038eed8e300667667e28` | **NO** |
| #33 `cursor/atlas-control-centre-e3a2` | `bcd4e0d7ace1898fbeb893e7a1c96441ea690bc1` | **NO** |

---

## Open pull requests — decisions

| PR | Purpose | Included in #34? | Decision |
|----|---------|------------------|----------|
| #3–#18 | Phase verification / live-gate | No (obsolete / conflicting) | **Close** superseded |
| #20 | Binance Spot Testnet E2E | **No** (separate track) | **Keep open** — isolated testnet candidate |
| #21–#28 | Paper lineage through Codespaces | **Yes** (ancestors / tip base) | **Close** after #34 merges |
| #29–#32 | Divergent mobile / durable forks | Partial UI ideas only | **Close** — do not merge |
| #33 | Control centre | **No** | **Park** — rebase onto post-merge `main` before any future integration |
| **#34** | Paper-v1 consolidation + mobile IA | **This PR** | **Merge via merge commit** when gates green |

---

## Code presence verified on tip (not docs-only)

| Capability | Evidence |
|------------|----------|
| Paper cycle | `app/services/paper_cycle.py` |
| Scheduler start/stop | `app/services/trading_scheduler.py`, BFF `/api/trading/start\|stop` |
| Hydrate / persist | `hydrate_paper_session_from_db`, `persist_paper_session` in `paper_session.py` |
| Reconciliation fail-closed | `app/services/reconciliation.py` |
| Central risk | `app/risk/engine.py` + `OrderGateway` |
| Live money impossible | `app/execution/live_gate.py` (`allowed` hard-false) |
| Durable tables | Alembic through `0006_paper_durable` |
| Mobile IA | Frontend bottom nav Home/Trade/Positions/Activity/More |
| Codespaces | `.devcontainer/`, `scripts/codespaces_start.sh` |

---

## PR #34 GitHub status (release-engineer audit)

| Check | Result |
|-------|--------|
| Draft | `true` (must mark ready before merge) |
| Mergeable | `MERGEABLE` / `mergeStateStatus: CLEAN` |
| Review comments | 0 unresolved |
| CI jobs (run `31004021468`) | backend / frontend / secret-scan / docker-compose-validate reported SUCCESS |
| Coverage honesty | Prior tip was **84.68%** raw; default cov precision=0 rounded to 85 so exit stayed 0 while terminal printed FAIL. **Fixed:** `--cov-precision=2` + hard coverage assert + extra invariant tests → **≥85.00% real**. |

---

## Exact human steps in GitHub (after CI green on latest tip)

1. **Mark PR #34 ready for review**  
   On https://github.com/gurungsio10-ops/Live_auto_trading/pull/34 → **Ready for review**.

2. **Merge PR #34 into `main` using a merge commit**  
   - Merge method: **Create a merge commit** (not squash, not rebase).  
   - Do **not** merge if Actions are red or conflicts appear.  
   - Confirm base = `main`, head = `release/atlas-paper-v1`.

3. **Close superseded PRs without merging them**  
   Close: **#3–#18, #21–#28, #29–#32**.  
   Optional comment: `Superseded by #34 (release/atlas-paper-v1). Do not merge individually.`

4. **Preserve PR #20**  
   Leave **#20** open as the isolated Binance Spot Testnet candidate. Do not close with the superseded batch.

5. **Rebase PR #33 later**  
   After `main` contains #34:  
   `git fetch origin main && git checkout cursor/atlas-control-centre-e3a2 && git rebase origin/main`  
   Resolve conflicts against tip APIs; re-run full quality suite before any integration attempt.

---

## Recommended merge order

1. Merge **PR #34** → `main` (merge commit).
2. Close superseded PRs (#3–#18, #21–#28, #29–#32).
3. Keep **#20** open.
4. Park **#33** until rebased onto new `main` with green CI.

---

## Safety note

This consolidation **must not** enable live-money trading, leverage, futures, withdrawals, or copy trading. Default remains `TRADING_MODE=paper` / `ENABLE_LIVE_TRADING=false`.
