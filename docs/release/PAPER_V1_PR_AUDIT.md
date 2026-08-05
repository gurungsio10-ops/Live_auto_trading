# Paper V1 — Open PR Audit (evidence-based)

**Audit timestamp (UTC):** 2026-08-05T18:14:03Z  
**Authoritative release branch:** `release/atlas-paper-v1`  
**Authoritative tip after PR #35 integration:** `293244991e802350edf6d357c89980f907ac1f22`  
**Base for PR #34:** `origin/main` = `88c312e05d0e3e202214b446b8bfa824a3bd2b9c`  
**Method:** `git fetch --prune`, `git merge-base`, `git merge-base --is-ancestor`, `git rev-list --count`, `gh pr list --state open`

## Verdict

| Question | Answer | Evidence |
|----------|--------|----------|
| Latest authoritative implementation? | `release/atlas-paper-v1` (PR **#34**) after FF of PR **#35** | Tip `2932449`; main is strict ancestor (`rev-list main..release` = 39 after analytics) |
| Is PR #35 included in PR #34 tip? | **Yes** after this release pass | Pre-integration release tip `3fcfc20`; analytics tip `2932449`; `merge-base(release, analytics)=3fcfc20`; `git merge --ff-only` advanced release to `2932449` |
| Does PR #33 contain unique valuable work? | **Yes, but divergent** — control-centre UI on the #29–#32 premium UI fork | Tip `bcd4e0d` is **not** ancestor of release; 7 commits ahead of main, 38 behind release |
| Should PR #20 remain isolated? | **Yes — retain** for later Spot Testnet | Tip `a2144a5` not ancestor of release; 4 unique commits vs main |
| Completely superseded? | #3–#18 (conflicting phase/live-gate), #21–#28 (linear ancestors), #29–#32 (divergent UI) | See per-PR table |

```text
main (88c312e)
 └── #21 … #28 (linear paper lineage; all ancestors of release tip)
      └── release/atlas-paper-v1  ← PR #34
           └── + #35 analytics (2932449)  ← now on release tip

Retain isolated:  #20 Binance Spot Testnet
Rebase later:     #33 control-centre (on divergent #29–#32 UI line)
Close superseded: #3–#18, #21–#28, #29–#32; close #35 after inclusion
```

---

## Per-PR decisions

### PR #35 — merge (integrated)

| Field | Value |
|-------|-------|
| Source | `cursor/paper-performance-analytics-e3a2` |
| Target | `release/atlas-paper-v1` |
| Tip SHA | `293244991e802350edf6d357c89980f907ac1f22` |
| Purpose | Persistent paper sessions analytics: closed trades, performance metrics, reports, CSV/JSON export, mobile performance/trades UI |
| Unique commits vs pre-integration release (`3fcfc20`) | `2932449 feat: paper performance analytics journal, metrics, and dashboard` |
| `merge-base` vs release (pre) | `3fcfc20b94524d9d1236a0d58124c6d596c95b2a` |
| Included in authoritative release | **yes** (fast-forward into `release/atlas-paper-v1`) |
| Decision | **merge** (done via FF); close after #34 lands |

### PR #34 — merge (authoritative vehicle)

| Field | Value |
|-------|-------|
| Source | `release/atlas-paper-v1` |
| Target | `main` |
| Tip SHA (post #35) | `293244991e802350edf6d357c89980f907ac1f22` |
| Purpose | Authoritative Paper V1 consolidation (lineage #21–#28 + mobile IA + coverage honesty + analytics) |
| Unique commits vs main | 39 (includes analytics) |
| Included in authoritative release | **this is the release branch** |
| Decision | **merge** into `main` via merge commit when Actions green |

### PR #33 — rebase (do not merge into Paper V1)

| Field | Value |
|-------|-------|
| Source | `cursor/atlas-control-centre-e3a2` |
| Target | `main` |
| Tip SHA | `bcd4e0d7ace1898fbeb893e7a1c96441ea690bc1` |
| Purpose | Unified control-centre status/brain/decisions/connectors |
| Unique commits vs release tip | 7 (control-centre + divergent UI stack `#29–#32`) |
| `merge-base` vs release | `88c312e05d0e3e202214b446b8bfa824a3bd2b9c` (= main) |
| Tip ancestor of release? | **no** |
| Included in authoritative release | **no** |
| Decision | **rebase** onto post-#34 `main` later; not part of Paper V1 |

### PR #32 — close

| Field | Value |
|-------|-------|
| Source | `cursor/atlas-mobile-ops-ui-e3a2` |
| Target | `main` |
| Tip SHA | `9ebf4028d579f345ea65c6161c24b12c2b567739` |
| Purpose | Mobile-first Atlas ops UI redesign |
| Unique vs release | 6 commits on divergent UI line |
| `merge-base` vs release | `88c312e` (main) |
| Included | **no** |
| Decision | **close** — superseded by release mobile IA; do not merge wholesale |

### PR #31 — close

| Field | Value |
|-------|-------|
| Source | `cursor/durable-paper-platform-e3a2` |
| Target | `main` |
| Tip SHA | `ea5a449774a0e8f22c974ed8ba2a49364863838b` |
| Purpose | Divergent durable paper + premium UI |
| Unique vs release | 5 commits |
| `merge-base` vs release | `88c312e` |
| Included | **no** (release has independent durable recovery from #26 lineage) |
| Decision | **close** |

### PR #30 — close

| Field | Value |
|-------|-------|
| Source | `cursor/atlas-premium-ui-redesign-e3a2` |
| Target | `main` |
| Tip SHA | `a762b9954e09017af9f67da18992beacca2e33f5` |
| Purpose | Premium mobile-first UI redesign |
| Unique vs release | 3 commits |
| Included | **no** |
| Decision | **close** |

### PR #29 — close

| Field | Value |
|-------|-------|
| Source | `cursor/mobile-first-ui-redesign-e3a2` |
| Target | `main` |
| Tip SHA | `fc9d5354892c0f9b312a28de3288ac66f36e57ca` |
| Purpose | Premium mobile-first dashboard redesign |
| Unique vs release | 1 commit |
| Included | **no** |
| Decision | **close** |

### PR #28 — close (ancestor)

| Field | Value |
|-------|-------|
| Source | `cursor/codespaces-auto-start-e3a2` |
| Target | `main` |
| Tip SHA | `2ed644a5210ac04eb293443345473441106209b5` |
| Purpose | Codespaces auto-start for paper stack |
| Unique vs release | none (`tip_is_ancestor_of_release=yes`) |
| Evidence | `git merge-base --is-ancestor 2ed644a release/atlas-paper-v1` → yes |
| Included | **yes** |
| Decision | **close** after #34 merges |

### PR #27 — close (ancestor)

| Field | Value |
|-------|-------|
| Source | `cursor/release-paper-v1-consolidated-e3a2` |
| Target | `main` |
| Tip SHA | `18e1cb271e691f4a4b4ccd3b5648be9cefa1e689` |
| Purpose | Prior paper-v1 consolidation |
| Included | **yes** (ancestor) |
| Decision | **close** |

### PR #26 — close (ancestor)

| Field | Value |
|-------|-------|
| Source | `cursor/durable-paper-recovery-e3a2` |
| Target | `main` |
| Tip SHA | `d1a3b694ca357680b9a173b150cf6094401e832d` |
| Purpose | Durable paper trading recovery |
| Included | **yes** (ancestor) |
| Decision | **close** |

### PR #25 — close (ancestor)

| Field | Value |
|-------|-------|
| Source | `cursor/production-trading-engine-e3a2` |
| Target | `main` |
| Tip SHA | `d9866a4c8b9ebd011282fca44b34f96987b94900` |
| Purpose | Phase 2 paper production engine |
| Included | **yes** (ancestor) |
| Decision | **close** |

### PR #24 — close (ancestor)

| Field | Value |
|-------|-------|
| Source | `cursor/paper-consolidation-e3a2` |
| Target | `main` |
| Tip SHA | `7e82288ffc252b3d49be6673c38f02bb709f9136` |
| Purpose | Paper consolidation durable state/locks/recon |
| Included | **yes** (ancestor) |
| Decision | **close** |

### PR #23 — close (ancestor)

| Field | Value |
|-------|-------|
| Source | `cursor/production-readiness-e3a2` |
| Target | `main` |
| Tip SHA | `29107fed57921cad63afcbbf995cbb96ec4f3560` |
| Purpose | Production paper readiness: scheduler, hydrate, reconcile, compose |
| Included | **yes** (ancestor) |
| Decision | **close** |

### PR #22 — close (ancestor)

| Field | Value |
|-------|-------|
| Source | `feature/paper-trading-mvp` |
| Target | `main` |
| Tip SHA | `704826ec8861dfdf3ee6d727c731bc1d9f38faa0` |
| Purpose | Paper Trading MVP |
| Included | **yes** (ancestor) |
| Decision | **close** |

### PR #21 — close (ancestor)

| Field | Value |
|-------|-------|
| Source | `cursor/paper-trading-e2e-e3a2` |
| Target | `main` |
| Tip SHA | `d4801f18fd15e428168578eba86cf2a0d869173f` |
| Purpose | Paper E2E hardening, auth, live-gate, strategies |
| Included | **yes** (ancestor) |
| Decision | **close** |

### PR #20 — retain

| Field | Value |
|-------|-------|
| Source | `cursor/binance-spot-testnet-pipeline-e3a2` |
| Target | `main` |
| Tip SHA | `a2144a51354194ae3517038eed8e300667667e28` |
| Purpose | Binance Spot Testnet end-to-end pipeline (post-Paper V1) |
| Unique commits vs release | `a2144a5`, `fe355f7`, `0cbf960`, `73b0be1` |
| `merge-base` vs release | `88c312e` (main) |
| Tip ancestor of release? | **no** |
| Included | **no** |
| Decision | **retain** — isolated testnet candidate; do not merge into Paper V1 |

### PRs #18 … #3 — close (superseded / conflicting)

All target `main`, `mergeable=CONFLICTING` (except where noted), merge-base vs release tip = `8f916314c1f8eb1a0a723172221a31a72be8264f` (pre-paper-v1 main ancestor). None are ancestors of `release/atlas-paper-v1`.

| PR | Source branch | Tip SHA | Purpose | Included | Decision |
|----|---------------|---------|---------|----------|----------|
| #18 | `cursor/live-gate-hardening-dc9d` | `1e33096b9c03cb5c89a39a7d430836c799524f16` | Live gating hardening | no | **close** |
| #17 | `cursor/phase15-verification-dc9d` | `def12370f9bb82de8599e0d1ea34ea182d0566ff` | Futures/leverage primitives verify | no | **close** (out of Paper V1 scope) |
| #16 | `cursor/phase14-verification-dc9d` | `cb5223c145cbcca47bc17ed2aa703e7ebe30c4b7` | Live trading prep verify | no | **close** |
| #15 | `cursor/phase13-5-verification-dc9d` | `f5e8609a3faf8fb7c5d6bdeba706656816109135` | Testnet execution verify | no | **close** |
| #14 | `cursor/phase13-verification-dc9d` | `4d963f3a07e25b7a3b742338f2a56ee0d92ae445` | News sentiment verify | no | **close** |
| #13 | `cursor/phase12-verification-dc9d` | `c7fd15812983c8504d3c8e331b164de91dce7f36` | Advisory AI isolation | no | **close** |
| #12 | `cursor/phase11-verification-dc9d` | `fdb161c04cf3f1ce8faf4231e675251804ee7c21` | Dashboard paper-safe UI | no | **close** |
| #11 | `cursor/phase10-verification-dc9d` | `24bbac23929075f4e3eaa19ff8aa659b2e4deebd` | Monitoring readiness | no | **close** |
| #10 | `cursor/phase9-verification-dc9d` | `f8379109e292d4c5872d0f9cc66b044b743a7171` | Journal/drawdown | no | **close** |
| #9 | `cursor/phase8-verification-dc9d` | `cc6c9323f95054db526fc1a915860bc54d77395a` | WebSocket feed | no | **close** |
| #8 | `cursor/phase7-verification-dc9d` | `26cb68ceebde1c34febf0ee54fd6a0c8f7abfbf0` | Paper fill failure | no | **close** |
| #7 | `cursor/phase6-verification-dc9d` | `227b7d867f237fa892ef140392e497a822187282` | Risk engine verify | no | **close** |
| #6 | `cursor/phase5-verification-dc9d` | `8ae35a841656a6b3ca8ce7788281e4c03a91944e` | Backtest costs/replay | no | **close** |
| #5 | `cursor/phase4-verification-dc9d` | `c941cb93877e649582db48dda84a3597353130a9` | Strategy registry | no | **close** |
| #4 | `cursor/phase3-verification-dc9d` | `5657bc9bdc2c31158e0a4916492cbe3d2c1ccb4c` | Indicators | no | **close** |
| #3 | `cursor/phase2-verification-dc9d` | `a2d486f948e1fca88727585daf40a83d7701fa3b` | Postgres/BinanceUS sync | no | **close** |

---

## Commands used (reproducible)

```bash
git fetch origin --prune
gh pr list --state open --limit 100 --json number,title,headRefName,baseRefName,mergeable,headRefOid
git merge-base origin/release/atlas-paper-v1 <tip>
git merge-base --is-ancestor <tip> origin/release/atlas-paper-v1
git rev-list --count origin/release/atlas-paper-v1..<tip>
git checkout release/atlas-paper-v1
git merge --ff-only origin/cursor/paper-performance-analytics-e3a2
# tip -> 293244991e802350edf6d357c89980f907ac1f22
```
