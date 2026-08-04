# Paper V1 Release Merge Plan

**Release branch:** `cursor/release-paper-v1-consolidated-e3a2`  
*(Semantic name: `release/paper-v1-consolidated`; cloud-agent branch policy requires `cursor/*-e3a2`.)*  
**Authoritative PR:** **#27** → `main`  
**Constraint:** PAPER ONLY — no live money, futures, leverage >1x, withdrawals, or autonomous AI execution.

**Exact human checklist:** [`docs/releases/pr27_merge_close_checklist.md`](../releases/pr27_merge_close_checklist.md)

## 1. Which PR/branch to merge

| Action | Target |
|--------|--------|
| **MERGE** | PR **#27** from `cursor/release-paper-v1-consolidated-e3a2` → `main` (squash) |
| Upstream tip absorbed | PR **#26** (all of #21–#25 are ancestors) |

Do **not** merge #21–#26 separately; they are linear ancestors of #27.

## 2. Older PRs to close as superseded

Close after the release merge lands on `main`:

- #21, #22, #23, #24, #25, #26 — superseded / absorbed
- #3–#18 phase/verification PRs still open — close as historical (optional)
- **#20 (binance testnet) — OUT OF SCOPE** — leave open; do not close as part of paper-v1

## 3. Squash vs regular merge

**Recommendation: squash merge** into `main`.

Rationale:

- Lineage #21…#26 already contains many iterative commits and docs churn
- Squash yields one authoritative paper-v1 commit on `main`
- Avoids replaying intermediate migration/WIP noise

Regular merge is acceptable only if the team wants to preserve the full PR DAG for archaeology.

## 4. Exact pre-merge commands

```bash
git fetch origin
git checkout cursor/release-paper-v1-consolidated-e3a2
git pull origin cursor/release-paper-v1-consolidated-e3a2
source .venv/bin/activate
pip install -e ".[dev]"
npm --prefix frontend ci

# Quality gates (must all pass)
ruff check app tests
ruff format --check app tests
mypy app
pytest -q
pytest --cov=app --cov-report=term-missing --cov-fail-under=85
alembic upgrade head   # with a fresh DATABASE_URL
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
docker compose -f docker-compose.yml config >/dev/null

# Optional short soak (no exchange credentials)
python -m app.cli paper-soak --duration-hours 0.01 --seed 42 --max-cycles 6
```

CI on the PR must be green (backend, frontend, secret-scan, docker-compose-validate).

## 5. Exact post-merge smoke tests

```bash
# On main after merge
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 &
curl -sf http://127.0.0.1:8000/health | jq .
curl -sf http://127.0.0.1:8000/api/v1/recovery/status | jq .
curl -sf -X POST http://127.0.0.1:8000/api/v1/paper/cycle/run \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -d '{"confirm":"RUN_ONE_CYCLE"}' | jq .
# Restart process, confirm cash/positions/kill-switch survive via recovery status
```

Dashboard: open `/recovery`, confirm runtime/recon/persistence fields populate. Mutating clear-halt requires admin BFF token (never browser-exposed).

## 6. Rollback procedure

1. Revert the squash merge commit on `main` (or redeploy previous SHA).
2. If migration `0006_paper_durable` already applied in an environment that must roll back schema:
   ```bash
   alembic downgrade 0005_cycle_ops
   ```
   Prefer forward-fix over downgrade in shared Postgres.
3. Keep trading paused / kill-switch active until recovery status is healthy.
4. Do **not** invent balances; restore from DB backup if dual-write corruption is suspected.

## 7. Known limitations

- Live money remains hard-blocked (`LiveTradingGate` never allows)
- Futures, leverage >1x, withdrawals unavailable
- AI is advisory only
- Scheduler disabled by default (`ENABLE_TRADING_SCHEDULER=false`)
- Public CCXT OHLCV is optional; offline fixtures are the default paper path
- Redis configured but not required at startup
- MVP `/api/*` aliases remain for ops checklists; `/api/v1` + dashboard are primary

## 8. Next milestone after consolidation

1. Reserved capital / buying-power accounting (implemented on this lineage — see paper engine)
2. Multi-day PostgreSQL soak under supervision (`paper-soak --duration-hours 24`)
3. Hardening of alert delivery + ops paging
4. Optional Binance/Bybit **testnet** execution path behind explicit gates (still no live money) — PR #20
5. Only after signed `docs/operations/live_trading_readiness_checklist.md`: consider live design review (not implementation)

## Disposition summary

| PR | Disposition |
|----|-------------|
| **#27** (this branch) | **MERGE** (squash) |
| #26 | close after merge (absorbed) |
| #21–#25 | **close after merge** (superseded) |
| #20 | **out of scope** — leave open |
| #3–#18 | close as historical (optional) |
