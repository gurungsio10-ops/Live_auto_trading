# PR #26 Consolidation & Merge-Readiness Report

**Branch:** `cursor/durable-paper-recovery-e3a2`  
**PR:** https://github.com/gurungsio10-ops/Live_auto_trading/pull/26  
**Constraint:** `TRADING_MODE=paper` only. No live-money execution.

## 1. PR comparison matrix

| PR | Branch | Focus | Migrations | Durable state | Cycle locks | Risk | API | Frontend | Disposition |
|----|--------|-------|------------|---------------|-------------|------|-----|----------|-------------|
| #21 | `cursor/paper-trading-e2e-e3a2` | Auth, live-gate, strategies, paper E2E base | — | Checkpoint v1 | — | ✓ | ✓ | ✓ | **Close — superseded** |
| #22 | `feature/paper-trading-mvp` | Paper MVP + broker/Bybit + `/api` MVP | — | Session share | — | ✓ | +mvp | ✓ | **Close — superseded** |
| #23 | `cursor/production-readiness-e3a2` | Scheduler, hydrate, recon, compose | — | Journal hydrate | — | recon→risk | health/metrics | fail-closed GETs | **Close — superseded** |
| #24 | `cursor/paper-consolidation-e3a2` | Control-plane consolidation | **0005** | Pause/kill SSOT | **DB locks** | halt | recon APIs | status/recon UI | **Close — superseded** |
| #25 | `cursor/production-trading-engine-e3a2` | MD hub, pool, portfolio, SSE | 0005 | same as #24 | fail-closed locks | exposure | AI/SSE | ops stream | **Close — superseded** |
| #26 | `cursor/durable-paper-recovery-e3a2` | Restart-safe durable recovery | **0005+0006** | First-class tables + atomic persist | ✓ | risk_state persisted | recovery/clear-halt | inherits #24/#25 | **MERGE** |

**Lineage fact:** `#21 ⊂ #22 ⊂ #23 ⊂ #24 ⊂ #25 ⊂ #26` (strict linear tip ancestry). Path-set `|⋃(#21…#25) − #26| = 0`.

## 2. Files retained from each PR

- **#21:** auth/BFF hardening, strategies, live-gate hard-block, restart-recovery test base, CI gitleaks
- **#22:** `app/api/mvp.py`, paper broker, Bybit facade, SafetyGuard, Makefile/Dockerfile
- **#23:** trading scheduler, reconciliation service, compose API, webhook alerts
- **#24:** Alembic 0005, `cycle_lock.py`, endurance/control-plane tests, ops dashboard recon
- **#25:** shared DB pool, MarketDataHub, PortfolioManager, ops SSE, advisory AI, CORS allowlist
- **#26-only:** Alembic 0006, `app/repositories/*`, durable hydrate/persist, recovery APIs, broker SL/TP realism, merge verification tests

## 3. Duplicate code removed

No parallel modules were copied. Consolidation is by **lineage containment**, not cherry-pick. Authoritative SSOT per subsystem:

| Subsystem | Authority |
|-----------|-----------|
| Risk | `app/risk/engine.py` via `OrderGateway` |
| Paper ledger | `PaperTradingEngine` + `paper_persistence` dual-write |
| Cycle | `run_paper_trading_cycle` |
| Recon | `app/services/reconciliation.py` |
| Runtime session | `PaperSession` singleton + hydrate/bootstrap |

Overlapping older PR tips are closed, not merged alongside #26.

## 4. Migration conflicts resolved

- Chain verified empty → head: `0001 → 0002 → 0003 → 0004 → 0005 → 0006`
- Downgrade `0006 → 0005` and re-upgrade `0005 → 0006` verified on **SQLite** and **PostgreSQL**
- No duplicate table / index / constraint names in Postgres catalogs
- ORM columns for 0006 models match migrated SQLite schema
- Migrations use dialect-neutral `sa.JSON` / `Numeric` / timezone `DateTime`

## 5. Tests added or corrected

- `tests/integration/test_merge_verification.py` — full durable restart matrix, recon halt blocks cycle, clear-halt admin auth, risk gateway non-bypass, duplicate fill idempotency, fail-closed helper, alembic file chain
- Existing durable/recovery/broker realism suites retained
- Dual-write hardening: `persist_paper_session` single commit; cycle persist/recon failures call `_fail_closed_persistence`

## 6. Final quality-gate results (local)

| Gate | Result |
|------|--------|
| `pytest -q` | **219 passed** |
| `ruff check app tests` | pass |
| `ruff format --check app tests` | pass |
| `mypy app` | pass |
| `alembic upgrade head` | `0006_paper_durable` |
| SQLite up/down/up | pass |
| PostgreSQL up/down/up | pass |
| `npm --prefix frontend run lint` | pass |
| `npm --prefix frontend run typecheck` | pass |
| `npm --prefix frontend run build` | pass |
| GitHub Actions on PR #26 | **all jobs green** (backend, frontend, secret-scan, docker-compose-validate) on tip `709e27d` |

## 7. Remaining known limitations

- Equity snapshots append on every persist (retention/pruning deferred)
- Auto-journal skipped for `:memory:` SQLite (pytest isolation by design)
- In-memory fill that precedes a failed durable write is compensated by fail-closed halt (not automatic ledger rewind)
- Live money / futures / leverage remain intentionally disabled

## 8. Recommendation

**MERGE** PR #26 into `main`.

## 9. Superseded PRs safe to close

Close after #26 merges (or immediately as superseded drafts):

- #21, #22, #23, #24, #25

Do **not** auto-close #20 (Binance testnet pipeline) or earlier phase verification PRs without a separate review — they are outside the 21–26 paper lineage.

## 10. Post-merge verification procedure for `main`

```bash
git checkout main && git pull origin main
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head          # expect 0006_paper_durable
pytest -q
ruff check app tests && ruff format --check app tests && mypy app
npm --prefix frontend ci
npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend run build

# Smoke durable path
uvicorn app.main:app --reload   # terminal A
# terminal B:
curl -s localhost:8000/api/v1/recovery/status | jq .
curl -s -X POST localhost:8000/api/v1/paper/cycle/run \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"symbol":"BTC/USDT","timeframe":"1m"}' | jq .
# restart API process, then:
curl -s localhost:8000/api/v1/portfolio | jq .
curl -s localhost:8000/api/v1/recovery/status | jq .
# Confirm cash/positions/kill-switch/recon match pre-restart durable state
```

Optional Postgres: point `DATABASE_URL` at Postgres, `alembic upgrade head`, repeat smoke.
