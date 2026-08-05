# PR Consolidation Audit — Project Atlas

**Audit date:** 2026-08-05 (UTC)  
**Consolidation tip:** `release/atlas-paper-v1` ← `origin/cursor/codespaces-auto-start-e3a2` (PR #28 tip `2ed644a`)  
**Base:** `origin/main`

## Executive summary

Verified via `git fetch`, `git merge-base --is-ancestor`, and `gh pr list`:

1. **Linear paper lineage:** `#21 ⊂ #22 ⊂ #23 ⊂ #24 ⊂ #25 ⊂ #26 ⊂ #27 ⊂ #28`
2. **PR #23 is NOT the tip.** It is an ancestor of #27/#28. All of #23’s production-paper work (scheduler, hydrate, reconcile, compose) is included in the consolidation tip.
3. **Best verified paper backend tip:** PR **#28** (`cursor/codespaces-auto-start-e3a2`) — 32 commits ahead of `main`, CI green (backend, frontend, secret-scan, docker-compose-validate).
4. **UI-only divergences (#29–#33)** fork from `main` / earlier tips and often lack the full strategy set (EMA+RSI, RSI mean reversion, Donchian) present on #27/#28. Backend CI is red on #31–#33. Do **not** merge them wholesale onto main.
5. **Phase verification PRs #3–#18** are obsolete / conflicting against current `main`. Close as superseded.
6. **PR #20** (Binance Spot Testnet) is a separate track — keep open until intentionally merged after paper-v1.

---

## Lineage diagram

```text
main
 └── #21 paper-trading-e2e
      └── #22 feature/paper-trading-mvp
           └── #23 production-readiness   ← user-cited candidate (INCLUDED)
                └── #24 paper-consolidation
                     └── #25 production-trading-engine
                          └── #26 durable-paper-recovery
                               └── #27 release-paper-v1-consolidated
                                    └── #28 codespaces-auto-start  ← AUTHORITATIVE TIP
                                         └── release/atlas-paper-v1 (+ mobile UI + docs)

Parallel / divergent (do not replace tip):
  #20 testnet pipeline (separate)
  #29 / #30 premium mobile UI (main-fork UI)
  #31 durable-paper-platform (diverged + backend CI red)
  #32 atlas-mobile-ops-ui (UI polish on #31 line; backend CI red)
  #33 atlas-control-centre (control-centre on #32 line; backend CI red)

Obsolete conflicting verification:
  #3 … #18 (phase*-verification-dc9d, live-gate-hardening)
```

---

## Open pull requests

| PR | Branch | Purpose | Unique vs tip | Overlap | CI (last known) | Recommended action |
|----|--------|---------|---------------|---------|-----------------|-------------------|
| #3 | `cursor/phase2-verification-dc9d` | Phase 2 verification | None useful | Superseded by paper lineage | CONFLICTING / stale | **Close** superseded |
| #4 | `cursor/phase3-verification-dc9d` | Indicators verification | None | Superseded | CONFLICTING | **Close** |
| #5 | `cursor/phase4-verification-dc9d` | Strategy registry verification | None | Superseded | CONFLICTING | **Close** |
| #6 | `cursor/phase5-verification-dc9d` | Backtest verification | None | Superseded | CONFLICTING | **Close** |
| #7 | `cursor/phase6-verification-dc9d` | Risk engine verification | None | Superseded | CONFLICTING | **Close** |
| #8 | `cursor/phase7-verification-dc9d` | Paper fill coverage | None | Superseded | CONFLICTING | **Close** |
| #9 | `cursor/phase8-verification-dc9d` | WebSocket coverage | None | Superseded | CONFLICTING | **Close** |
| #10 | `cursor/phase9-verification-dc9d` | Journal / drawdown | None | Superseded | CONFLICTING | **Close** |
| #11 | `cursor/phase10-verification-dc9d` | Monitoring / alerts | None | Superseded | CONFLICTING | **Close** |
| #12 | `cursor/phase11-verification-dc9d` | Dashboard verification | None | Superseded | CONFLICTING | **Close** |
| #13 | `cursor/phase12-verification-dc9d` | Advisory AI isolation | None | Superseded | CONFLICTING | **Close** |
| #14 | `cursor/phase13-verification-dc9d` | News sentiment | None | Superseded | CONFLICTING | **Close** |
| #15 | `cursor/phase13-5-verification-dc9d` | Testnet execution verify | Partial docs only | CONFLICTING | **Close** (keep #20 for testnet) |
| #16 | `cursor/phase14-verification-dc9d` | Live prep gates | None (live remains disabled) | CONFLICTING | **Close** |
| #17 | `cursor/phase15-verification-dc9d` | Futures/leverage primitives | Intentionally unwired | CONFLICTING | **Close** — do not enable futures |
| #18 | `cursor/live-gate-hardening-dc9d` | Live gate hardening | Largely absorbed into #21+ | CONFLICTING | **Close** |
| #20 | `cursor/binance-spot-testnet-pipeline-e3a2` | Binance Spot Testnet E2E | Testnet connector path | Separate from paper tip | Green | **Keep open** — merge after paper-v1 if desired |
| #21 | `cursor/paper-trading-e2e-e3a2` | Paper E2E hardening | Ancestor of tip | Fully in #28 | Green (secret-scan fail historically) | **Close** superseded by #28 |
| #22 | `feature/paper-trading-mvp` | Paper MVP | Ancestor | In tip | Partial | **Close** superseded |
| #23 | `cursor/production-readiness-e3a2` | Scheduler, hydrate, reconcile, compose | Ancestor (~10 commits behind tip after #23) | Fully in tip | Green historically | **Close** superseded — **do not merge alone** |
| #24 | `cursor/paper-consolidation-e3a2` | Durable locks / recon / ops | Ancestor | In tip | Partial secret-scan | **Close** superseded |
| #25 | `cursor/production-trading-engine-e3a2` | MD hub, pool, portfolio, SSE | Ancestor | In tip | secret-scan fail | **Close** superseded |
| #26 | `cursor/durable-paper-recovery-e3a2` | Restart-safe durable paper | Ancestor | In tip | Green | **Close** superseded |
| #27 | `cursor/release-paper-v1-consolidated-e3a2` | Authoritative paper consolidate | Tip − Codespaces | In #28 | Green | **Close** superseded by #28 / release branch |
| #28 | `cursor/codespaces-auto-start-e3a2` | Codespaces + paper tip | Base of `release/atlas-paper-v1` | Canonical | **Green** | **Merge via release PR** (or close after release merges) |
| #29 | `cursor/mobile-first-ui-redesign-e3a2` | Premium mobile UI | Divergent UI | Overlaps IA ideas | Green | **Close** — extract ideas only; do not merge wholesale |
| #30 | `cursor/atlas-premium-ui-redesign-e3a2` | Premium UI redesign | Divergent | Overlaps #29 | Green | **Close** — extract ideas only |
| #31 | `cursor/durable-paper-platform-e3a2` | Persistence / analytics fork | Diverged APIs | Conflicts with tip strategies | Backend **FAILURE** | **Close** — do not merge |
| #32 | `cursor/atlas-mobile-ops-ui-e3a2` | Mobile ops UI on #31 line | Bottom nav / cards | UI ideas useful | Backend **FAILURE** | **Close** — concepts ported to release branch |
| #33 | `cursor/atlas-control-centre-e3a2` | Control centre / brain / connectors | New ops concepts | Diverged | Backend **FAILURE** | **Close** or park — cherry-pick later after green tip |

---

## PR #23 vs tip (verified)

| Check | Result |
|-------|--------|
| `merge-base --is-ancestor production-readiness HEAD` | **YES** |
| Commits on tip after #23 tip | Codespaces, reserved capital, consolidation audits, durable recovery, Phase 2 engine, … |
| Strategies on tip | `ema_crossover`, `ema_rsi`, `rsi_mean_reversion`, `breakout` (Donchian) |
| Scheduler / hydrate / reconcile | Present (`trading_scheduler.py`, paper persistence, reconciliation) |

**Conclusion:** Treat #23 as historically important but **superseded**. Consolidation candidate is **#28 → `release/atlas-paper-v1`**.

---

## Conflicting implementations

| Area | Conflict | Resolution on release branch |
|------|----------|------------------------------|
| Frontend IA | Terminal sidebar (#28) vs premium bottom-nav (#29–#32) | Bottom nav Home/Trade/Positions/Activity/More on #28 APIs |
| Backend control-centre (#33) | New brain/decision tables vs tip | **Deferred** — tip APIs remain canonical |
| Testnet (#20) | Binance testnet vs paper offline | Keep separate; paper default remains |
| Live gate PRs (#16–#18) | Overlapping gate checklists | Tip `LiveTradingGate` + `ENABLE_LIVE_TRADING=false` |

---

## Changes present in #23 missing from `main` (now on tip)

All of the following land on `main` only via merging the release branch (they are **not** on bare `main` today):

- Continuous trading scheduler with start/stop
- Startup hydrate + fail-closed reconciliation
- Docker Compose paper stack
- Production readiness docs / ops notes
- Durable paper cycle path improvements introduced through #24–#28

---

## Recommended merge order

1. Merge **`release/atlas-paper-v1`** → `main` (this PR).
2. Close superseded PRs listed above (#3–#18, #21–#28, #29–#32; optionally #33).
3. Optionally follow with **#20** testnet behind feature flags after paper-v1 is stable.
4. Optionally cherry-pick control-centre ideas from #33 onto post-merge `main` only after tests are green.

---

## Safety note

This consolidation **must not** enable live-money trading, leverage, futures, withdrawals, or copy trading. Default remains `TRADING_MODE=paper` / `ENABLE_LIVE_TRADING=false`.
