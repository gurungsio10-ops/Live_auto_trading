# PR Consolidation Audit — `release/atlas-paper-v1`

**Audit date:** 2026-08-05 (UTC)  
**Repo:** `gurungsio10-ops/Live_auto_trading`  
**Base compared:** `origin/main` @ `88c312e` (`Phase 16: audit + end-to-end paper-trading validation (#19)`)  
**Method:** `gh pr list/view/checks` + `git fetch` / `git rev-list` / `git merge-base --is-ancestor` / `git diff --stat` / path & registry inspection  
**Constraint:** PAPER ONLY — no live money, futures, leverage >1x, withdrawals, or autonomous AI execution.

---

## 1. All open PRs

| PR | Title | `headRefName` | Draft | Mergeable | CI conclusion summary |
|----|-------|---------------|-------|-----------|------------------------|
| #3 | Phase 2 verification: Postgres migrate + BinanceUS OHLCV sync | `cursor/phase2-verification-dc9d` | yes | CONFLICTING | no checks |
| #4 | Phase 3 verification: indicators Decimal/validation coverage | `cursor/phase3-verification-dc9d` | yes | CONFLICTING | no checks |
| #5 | Phase 4 verification: strategy registry, determinism, exits | `cursor/phase4-verification-dc9d` | yes | CONFLICTING | no checks |
| #6 | Phase 5 verification: backtest costs, replay, no look-ahead | `cursor/phase5-verification-dc9d` | yes | CONFLICTING | no checks |
| #7 | Phase 6 verification: risk engine 95% coverage, reject reason codes | `cursor/phase6-verification-dc9d` | yes | CONFLICTING | no checks |
| #8 | Phase 7: paper fill failure fix + 100% paper coverage | `cursor/phase7-verification-dc9d` | yes | CONFLICTING | no checks |
| #9 | Phase 8 verification: WebSocket feed coverage 94% | `cursor/phase8-verification-dc9d` | yes | CONFLICTING | no checks |
| #10 | Phase 9 verification: journal reason codes + portfolio drawdown | `cursor/phase9-verification-dc9d` | yes | CONFLICTING | no checks |
| #11 | Phase 10 verification: monitoring readiness + alerts 100% | `cursor/phase10-verification-dc9d` | yes | CONFLICTING | no checks |
| #12 | Phase 11 verification: dashboard build/lint + paper-safe UI | `cursor/phase11-verification-dc9d` | yes | CONFLICTING | no checks |
| #13 | Phase 12 verification: advisory AI isolation + API labels | `cursor/phase12-verification-dc9d` | yes | CONFLICTING | no checks |
| #14 | Phase 13 verification: news sentiment 100% coverage | `cursor/phase13-verification-dc9d` | yes | CONFLICTING | no checks |
| #15 | Phase 13.5: verify testnet execution (coverage ≥90%) | `cursor/phase13-5-verification-dc9d` | **no** | CONFLICTING | no checks |
| #16 | Phase 14: verify live trading preparation (9 gates hardened) | `cursor/phase14-verification-dc9d` | yes | CONFLICTING | no checks |
| #17 | Phase 15: verify futures/leverage primitives (unwired, 1x default) | `cursor/phase15-verification-dc9d` | yes | CONFLICTING | no checks |
| #18 | Harden live gating: Settings SoT, hmac tokens, fail-closed recon | `cursor/live-gate-hardening-dc9d` | yes | CONFLICTING | no checks |
| #20 | feat: Binance Spot Testnet end-to-end trading pipeline (Sprint 1) | `cursor/binance-spot-testnet-pipeline-e3a2` | yes | MERGEABLE | all-green (backend, frontend) |
| #21 | Atlas production hardening: paper E2E, auth, live-gate, strategies, docs | `cursor/paper-trading-e2e-e3a2` | yes | MERGEABLE | secret-scan=FAILURE; backend/frontend/docker-compose-validate=SUCCESS |
| #22 | Paper Trading MVP: end-to-end simulated trading path | `feature/paper-trading-mvp` | yes | MERGEABLE | secret-scan=FAILURE; backend/frontend/docker-compose-validate=SUCCESS |
| #23 | Production paper readiness: scheduler, hydrate, reconcile, compose | `cursor/production-readiness-e3a2` | yes | MERGEABLE | secret-scan=FAILURE; backend/frontend/docker-compose-validate=SUCCESS |
| #24 | feat: paper trading consolidation — durable state, locks, recon, ops dashboard | `cursor/paper-consolidation-e3a2` | yes | MERGEABLE | secret-scan=FAILURE; backend/frontend/docker-compose-validate=SUCCESS |
| #25 | feat: Phase 2 paper production engine (MD hub, pool, portfolio, SSE) | `cursor/production-trading-engine-e3a2` | yes | MERGEABLE | secret-scan=FAILURE; backend/frontend/docker-compose-validate=SUCCESS |
| #26 | feat: Durable paper trading recovery — MERGE READY (#26) | `cursor/durable-paper-recovery-e3a2` | yes | MERGEABLE | **all-green** (backend, frontend, secret-scan, docker-compose-validate) |
| #27 | consolidate: authoritative paper-trading platform (PR #25+#26 lineage) | `cursor/release-paper-v1-consolidated-e3a2` | yes | MERGEABLE | **all-green** (4 checks) |
| #28 | Add Codespaces auto-start for paper development stack | `cursor/codespaces-auto-start-e3a2` | yes | MERGEABLE | **all-green** (4 checks) |
| #29 | Premium mobile-first Atlas dashboard redesign | `cursor/mobile-first-ui-redesign-e3a2` | yes | MERGEABLE | all-green (backend, frontend) |
| #30 | Premium mobile-first Project Atlas UI redesign | `cursor/atlas-premium-ui-redesign-e3a2` | yes | MERGEABLE | all-green (backend, frontend) |
| #31 | Durable paper platform: persistence, scheduler, analytics, ops hardening | `cursor/durable-paper-platform-e3a2` | yes | MERGEABLE | backend=FAILURE; frontend=SUCCESS |
| #32 | Mobile-first Atlas ops UI redesign | `cursor/atlas-mobile-ops-ui-e3a2` | yes | MERGEABLE | backend=FAILURE; frontend=SUCCESS |
| #33 | Atlas control centre: truthful status, brain, decisions, connectors | `cursor/atlas-control-centre-e3a2` | yes | MERGEABLE | backend=FAILURE (ruff import order); frontend=SUCCESS |

**Already merged (context):** #2 (Phase 1 verification), #19 (Phase 16 audit + paper E2E → current `main`).

---

## 2. Key branches vs `origin/main`

| PR | Branch tip (short) | Ahead | Behind | Files changed | Diff `--shortstat` |
|----|--------------------|------:|-------:|--------------:|--------------------|
| #23 | `29107fe` `cursor/production-readiness-e3a2` | 10 | 0 | 84 | +5365 / −618 |
| #24 | `7e82288` `cursor/paper-consolidation-e3a2` | 13 | 0 | 103 | +7565 / −749 |
| #25 | `d9866a4` `cursor/production-trading-engine-e3a2` | 14 | 0 | 116 | +8767 / −755 |
| #26 | `d1a3b69` `cursor/durable-paper-recovery-e3a2` | 20 | 0 | 133 | +11239 / −764 |
| #27 | `18e1cb2` `cursor/release-paper-v1-consolidated-e3a2` | 30 | 0 | 191 | +16268 / −1065 |
| #28 | `2ed644a` `cursor/codespaces-auto-start-e3a2` | 32 | 0 | 197 | +16823 / −1059 |
| #29 | `fc9d535` `cursor/mobile-first-ui-redesign-e3a2` | 1 | 0 | 51 | +2580 / −648 |
| #30 | `a762b99` `cursor/atlas-premium-ui-redesign-e3a2` | 3 | 0 | 92 | +5509 / −1483 |
| #31 | `ea5a449` `cursor/durable-paper-platform-e3a2` | 5 | 0 | 133 | +8946 / −1511 |
| #32 | `9ebf402` `cursor/atlas-mobile-ops-ui-e3a2` | 6 | 0 | 146 | +10354 / −1497 |
| #33 | `bcd4e0d` `cursor/atlas-control-centre-e3a2` | 7 | 0 | 163 | +12270 / −1498 |

`#24` **exists** and is open.

---

## 3. Ancestry: PR #23 ⊂ #26 / #27?

| Check | Result |
|-------|--------|
| `git merge-base --is-ancestor origin/cursor/production-readiness-e3a2 origin/cursor/durable-paper-recovery-e3a2` | **YES** — #23 tip `29107fe` is ancestor of #26 tip `d1a3b69` |
| `git merge-base --is-ancestor … origin/cursor/release-paper-v1-consolidated-e3a2` | **YES** — #23 tip is ancestor of #27 tip `18e1cb2` |
| All 10 commits on #23 vs `main` contained in #26/#27 | **YES** (no missing SHAs) |
| `git branch -r --contains 29107fe` | `#23, #24, #25, #26, #27, #28` only (not UI lineage) |

### Paper lineage (linear)

```
main (88c312e)
  ⊂ #21 (d4801f1)
    ⊂ #22 (704826e)
      ⊂ #23 (29107fe)
        ⊂ #24 (7e82288)
          ⊂ #25 (d9866a4)
            ⊂ #26 (d1a3b69)
              ⊂ #27 (18e1cb2)
                ⊂ #28 (2ed644a)   ← tip of paper lineage
```

### UI / alternate-platform lineage (linear, **fully divergent** after `main`)

```
main (88c312e)
  ⊂ #29 (fc9d535)
    ⊂ #30 (a762b99)
      ⊂ #31 (ea5a449)
        ⊂ #32 (9ebf402)
          ⊂ #33 (bcd4e0d)
```

`merge-base(#28, #33) == origin/main` → **no shared commits after main**. File churn overlap is tiny (~21 shared paths vs ~176 only-in-#28 / ~142 only-in-#33). Treat as competing stacks, not incremental layers.

---

## 4. Paper-platform completeness matrix

| Capability | #23 | #24 | #25 | #26 | **#27** | **#28** | #30 | #31 | #32 | #33 |
|------------|:---:|:---:|:---:|:---:|:-------:|:-------:|:---:|:---:|:---:|:---:|
| EMA crossover | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| EMA+RSI (`ema_rsi`) | Y | Y | Y | Y | Y | Y | — | — | — | — |
| EMA trend | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| RSI mean reversion | Y | Y | Y | Y | Y | Y | — | — | — | — |
| Donchian breakout (`breakout.py`) | Y | Y | Y | Y | Y | Y | — | — | — | — |
| `trading_scheduler.py` (canonical) | Y | Y | Y | Y | Y | Y | — | — | — | — |
| `scheduler_service.py` (alt) | — | — | — | — | — | — | — | Y | Y | Y |
| Paper persistence / hydrate | Y | Y | Y | Y | Y | Y | — | Y* | Y* | Y* |
| Risk engine | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| Kill switch (API + UI) | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| Docker compose | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| Single `Dockerfile` | Y | Y | Y | Y | Y | Y | — | — | — | — |
| Split `Dockerfile.backend/.frontend` | — | — | — | — | — | — | — | Y | Y | Y |
| MD hub / portfolio / orchestrator | partial→ | → | Y | Y | Y | Y | — | alt | alt | alt |
| Recovery UI | — | — | — | — | Y | Y | — | — | — | — |
| Codespaces auto-start | — | — | — | — | — | **Y** | — | — | — | — |
| Premium / ops frontend pages | basic | basic | basic | basic | basic+ops | basic+ops | premium | premium+ops | premium+ops | **richest UI** |
| CI green (full 4-job set where present) | secret-scan fail | secret-scan fail | secret-scan fail | **green** | **green** | **green** | 2-job green | backend fail | backend fail | backend fail |

\* #31–#33 use a **different** Alembic chain (`0005_durable_ops` / `0006_paper_durable` / `0007_ensure_ops_tables`) and alternate services (`scheduler_service`, `paper_state_repository`) — not the #26/#27 dual-write recovery stack.

### Verdict: most complete paper platform

**Winner: `origin/cursor/codespaces-auto-start-e3a2` (PR #28)** — supersets #27, which supersets #26…#23.

It is the only tip that simultaneously has:

- Full strategy set: **EMA** (crossover/trend/ema_rsi), **RSI** mean reversion, **Donchian** breakout  
- Canonical `trading_scheduler` + cycle locks + reconciliation  
- Durable persistence / restart recovery (Alembic through paper account/risk/strategy state)  
- Risk engine + kill switch  
- Docker compose + Dockerfile  
- Production dashboard / recovery UI  
- Codespaces lifecycle scripts  
- **Green CI** (all 4 jobs)

#33 has the richest frontend/control-centre UX but is a **parallel incomplete rewrite** (missing 3 strategies, alternate scheduler/persistence, backend CI red).

---

## 5. Recommendation for `release/atlas-paper-v1`

| Decision | Choice |
|----------|--------|
| **Single best base branch** | **`cursor/release-paper-v1-consolidated-e3a2` (PR #27)** for the named paper-v1 product merge |
| **Best operational tip (DX)** | **`cursor/codespaces-auto-start-e3a2` (PR #28)** = #27 + 2 Codespaces commits; prefer this if Codespaces auto-start is in scope for the release cut |
| **Do not use as base** | #29–#33 (divergent after `main`); #23–#26 (strict ancestors of #27) |

### Merge / cherry-pick plan for later PRs (#28–#33)

| PR | Action relative to #27 base |
|----|-----------------------------|
| **#28** | **Merge or fast-forward on top** (already linear: `#27 ⊂ #28`). Lowest risk; green CI. Preferred release tip if DX scripts wanted. |
| **#29** | **Superseded by #30** within UI lineage. Do **not** merge onto #27 as-is (diverges from `main`). Optionally cherry-pick selected frontend-only commits after conflict resolution. |
| **#30** | **Cherry-pick UI/design-system files only** onto #27/#28 after release base lands. Skip any accidental backend churn. Expect heavy conflicts with #27 frontend. |
| **#31** | **Do not merge.** Parallel durable-paper rewrite conflicts with #26/#27 persistence/scheduler/migrations. Port *ideas* (analytics endpoints, scheduler admin UI) selectively if needed. |
| **#32** | **Cherry-pick frontend ops shell** (nav, overview, cards) onto #27/#28 *after* #30 design tokens, or re-implement against #27 APIs. Do not take #31 backend with it. |
| **#33** | **Cherry-pick control-centre UI + thin BFF routes** (brain/decisions/system-status pages) onto #27/#28; **re-implement** `atlas_brain` / `decision_feed` / unified status against #27 services. Fix ruff before any port. Do **not** merge branch wholesale. |

### Suggested release sequence

1. Squash-merge **#27** (or **#28** if Codespaces included) → `main` as `release/atlas-paper-v1`.  
2. Close #21–#26 as superseded (and #23–#25 intermediate tips).  
3. Open a follow-up branch from that tip for **Atlas UI**: port #30/#32/#33 frontend incrementally; keep #27 backend as SoT.  
4. Leave **#20** open (testnet pipeline; out of paper-v1 scope).  
5. Close #3–#18 as historical/conflicting verification.

---

## 6. PRs #2–#22 — disposition

| PR | State | Disposition | Notes |
|----|-------|-------------|-------|
| #2 | **MERGED** | done | Phase 1 verification |
| #3–#14 | OPEN / CONFLICTING | **verification-only / close** | Phase 2–13 verification drafts; no checks; superseded by later work + #19 |
| #15 | OPEN / CONFLICTING | **verification-only / close** | Phase 13.5; non-draft but conflicting; no checks |
| #16–#17 | OPEN / CONFLICTING | **verification-only / close** | Live-prep / futures primitives verification; unwired by design |
| #18 | OPEN / CONFLICTING | **superseded ideas / close** | Live-gate hardening; useful concepts already in paper lineage; do not merge branch |
| #19 | **MERGED** | done | Current `main` tip |
| #20 | OPEN / MERGEABLE / green | **keep open — out of scope** | Binance Spot Testnet pipeline; tip **not** in #27/#28; separate track |
| #21 | OPEN / MERGEABLE | **superseded by #27** | Tip `d4801f1` ⊂ #23 ⊂ #27; secret-scan red |
| #22 | OPEN / MERGEABLE | **superseded by #27** | Tip `704826e` ⊂ #23 ⊂ #27; secret-scan red |

---

## 7. Intermediate paper PRs (#23–#26) — close after #27/#28

| PR | Disposition |
|----|-------------|
| #23 | **Superseded** — full commit set is ancestor of #27/#26 |
| #24 | **Superseded** — consolidation + Alembic 0005 absorbed |
| #25 | **Superseded** — MD hub / pool / portfolio / SSE absorbed |
| #26 | **Superseded by #27** as release tip (still historically “MERGE READY”; #27 adds reserved capital, cycle guards, Codespaces auth polish, dashboard fixes) |

---

## 8. One-line executive summary

**Base `release/atlas-paper-v1` on PR #27 (or tip #28 for Codespaces); treat #29–#33 as a divergent UI fork to cherry-pick onto that base; close #3–#18 and #21–#26 as verification/superseded; leave #20 for testnet.**
