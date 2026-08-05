# PR #27 — Human Merge & Close Checklist

**Authoritative tip:** `cursor/release-paper-v1-consolidated-e3a2` @ `51a1dc4` (re-verify via `gh pr view 27`)  
**PR:** https://github.com/gurungsio10-ops/Live_auto_trading/pull/27 → `main`  
**Constraint:** PAPER ONLY — do not enable live money, futures, leverage >1x, withdrawals, or autonomous AI execution.

Verified at last agent pass: `MERGEABLE`, `mergeStateStatus=CLEAN`, CI jobs `backend` / `frontend` / `secret-scan` / `docker-compose-validate` all `SUCCESS` on `51a1dc4`.

---

## A. Pre-merge gates (human)

- [ ] `gh pr view 27 --json state,mergeable,mergeStateStatus,headRefOid,statusCheckRollup`
- [ ] Confirm `state=OPEN`, `mergeable=MERGEABLE`, `mergeStateStatus=CLEAN`
- [ ] Confirm all check conclusions are `SUCCESS`
- [ ] Skim diff: no live-execution enablement, no futures/leverage>1x, no withdrawal paths
- [ ] Optional local re-gate on the PR tip:

```bash
git fetch origin
git checkout cursor/release-paper-v1-consolidated-e3a2
git pull origin cursor/release-paper-v1-consolidated-e3a2
source .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=sqlite+aiosqlite:///:memory:
export TRADING_MODE=paper
export ADMIN_API_TOKEN=test-admin-token
ruff check app tests && ruff format --check app tests && mypy app
pytest -q --cov=app --cov-fail-under=85
npm --prefix frontend ci && npm --prefix frontend run lint && npm --prefix frontend run typecheck
```

---

## B. Squash-merge #27 into `main` (exact)

**Use GitHub UI “Squash and merge”** (recommended) or:

```bash
gh pr merge 27 --squash --delete-branch=false
```

Suggested squash title:

```text
consolidate: paper-trading V1 platform (durable recovery, canonical cycle, reserved capital)
```

After merge:

```bash
git fetch origin main
git checkout main
git pull origin main
alembic upgrade head   # expect head 0006_paper_durable
```

---

## C. Post-merge smoke (exact)

```bash
export TRADING_MODE=paper
export ADMIN_API_TOKEN=<your-admin-token>
export DATABASE_URL=<your-db-url>
uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -sf http://127.0.0.1:8000/health | jq .
curl -sf http://127.0.0.1:8000/api/v1/recovery/status | jq .
curl -sf -X POST http://127.0.0.1:8000/api/v1/paper/cycle/run \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -d '{"confirm":"RUN_ONE_CYCLE"}' | jq .
```

Dashboard: open `/recovery` — runtime / recon / persistence fields populate. Mutating clear-halt requires admin token (never browser-exposed).

---

## D. Close superseded PRs (exact list)

Close **after** #27 is on `main`. Do **not** merge these.

| PR | Branch | Action | Note |
|----|--------|--------|------|
| **#21** | `cursor/paper-trading-e2e-e3a2` | **CLOSE** | Superseded ancestor |
| **#22** | `feature/paper-trading-mvp` | **CLOSE** | Superseded ancestor |
| **#23** | `cursor/production-readiness-e3a2` | **CLOSE** | Superseded ancestor |
| **#24** | `cursor/paper-consolidation-e3a2` | **CLOSE** | Superseded ancestor |
| **#25** | `cursor/production-trading-engine-e3a2` | **CLOSE** | Superseded (insufficient alone — missing 0006) |
| **#26** | `cursor/durable-paper-recovery-e3a2` | **CLOSE** | Absorbed into #27 |
| **#20** | `cursor/binance-spot-testnet-pipeline-e3a2` | **LEAVE OPEN** | Out of paper-v1 scope (testnet milestone) |
| #3–#18 | phase verification branches | CLOSE as historical (optional cleanup) | Noise; not required for paper-v1 |

Example close commands (after #27 merge):

```bash
gh pr close 21 --comment "Superseded by squash-merge of #27 (paper V1 consolidated)."
gh pr close 22 --comment "Superseded by squash-merge of #27 (paper V1 consolidated)."
gh pr close 23 --comment "Superseded by squash-merge of #27 (paper V1 consolidated)."
gh pr close 24 --comment "Superseded by squash-merge of #27 (paper V1 consolidated)."
gh pr close 25 --comment "Superseded by squash-merge of #27 (paper V1 consolidated)."
gh pr close 26 --comment "Absorbed into #27; closed after paper V1 squash-merge."
# Do NOT close #20 as part of this release.
```

---

## E. Rollback

1. Revert the squash commit on `main` (or redeploy previous SHA).
2. If `0006_paper_durable` must be undone in an isolated env: `alembic downgrade 0005_cycle_ops` (prefer forward-fix in shared Postgres).
3. Keep trading paused / kill-switch active until recovery status is healthy.
4. Do not invent balances — restore from DB backup if dual-write corruption is suspected.

---

## F. Non-negotiables after merge

- `TRADING_MODE=paper` default
- Live execution remains hard-blocked
- AI advisory only
- Single canonical path: Candles → validate → strategy → OrderGateway → RiskEngine → PaperTradingEngine → invariants → dual-write → `/api/v1` + dashboard + `/recovery`
