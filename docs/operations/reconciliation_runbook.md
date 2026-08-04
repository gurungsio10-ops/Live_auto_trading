# Reconciliation runbook

## When it runs

- Startup (`bootstrap_paper_runtime`)
- After every completed paper cycle
- Periodic loop when `ENABLE_RECONCILIATION=true`
- On demand: `POST /api/reconciliation/run` (admin auth)

## On mismatch

1. System sets reconciliation halt (`risk_engine.state.reconciliation_healthy=false`)
2. New orders are blocked (fail closed)
3. Read endpoints remain available
4. `/ready` returns `not_ready`
5. Operators inspect mismatches (`expected` / `observed` / `difference`)
6. Correct root cause; do **not** silently overwrite ledger vs materialised cash
7. Clear halt only after a healthy reconciliation (`clear_reconciliation_halt` / successful run)

## Manual trigger

```bash
curl -X POST http://127.0.0.1:8000/api/reconciliation/run \
  -H 'X-Admin-Token: local-dev-admin-token'
```
