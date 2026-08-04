# Release Notes — Paper V1 Consolidation

**PR:** https://github.com/gurungsio10-ops/Live_auto_trading/pull/27  
**Branch:** `cursor/release-paper-v1-consolidated-e3a2`  
**Base tip ancestry:** PR #26 (durable recovery) ⊃ #25 ⊃ … ⊃ #21 ⊃ main

## What this release is

One authoritative, reproducible **paper-trading** platform:

- Deterministic offline cycles
- Durable paper account / risk / strategy state (Alembic `0006_paper_durable`)
- Fail-closed reconciliation and cycle locks
- Canonical risk gateway on every order
- Ops dashboard with Recovery panel
- Soak harness and accounting invariants
- CI gates including ≥85% app coverage + secret scan

## What this release is not

- Not live-money trading
- Not futures / leverage / withdrawals / deposits / copy trading
- Not autonomous AI execution

## Supersedes

Close after merge: PRs **#21, #22, #23, #24, #25, #26**.

## Upgrade

```bash
git checkout main && git pull
# after merge of #27
alembic upgrade head   # → 0006_paper_durable
```

## Smoke

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
curl -sf http://127.0.0.1:8000/health
curl -sf -X POST http://127.0.0.1:8000/api/v1/paper/cycle/run \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -d '{"confirm":"RUN_ONE_CYCLE"}'
```

## Merge recommendation

Squash-merge PR #27 into `main`. See `docs/audit/release_merge_plan.md` and `docs/audits/consolidation_audit.md`.
