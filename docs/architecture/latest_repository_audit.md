# Project Atlas — Latest Repository Audit

**Date:** 2026-08-05  
**Repository:** Live_auto_trading (Project Atlas)  
**Branch baseline:** `cursor/atlas-premium-ui-redesign-e3a2`  
**Auditor:** Autonomous cloud agent (production milestone)

## Current architecture

```
┌─────────────────┐     BFF /api/*      ┌──────────────────┐
│ Next.js 14 UI   │ ──────────────────► │ FastAPI backend  │
│ (paper desk)    │   ATLAS_BACKEND_URL │ app/main.py      │
└─────────────────┘                     └────────┬─────────┘
                                                 │
                    ┌────────────────────────────┼────────────────────────────┐
                    ▼                            ▼                            ▼
            Root dashboard API            /api/v1 paper slice          Auth /health
            (PaperSession)                (paper_cycle + session)      /ready
                    │                            │
                    ▼                            ▼
            OrderGateway ──► RiskEngine ──► PaperTradingEngine
                                                 │
                    JournalStore (optional) ◄────┘
                    SQLite/Postgres (Alembic 0001–0004)
```

- **Money path:** Decimal throughout risk + paper execution.
- **Live trading:** Fail-closed (`LiveTradingDisabledError`, `LiveTradingGate`).
- **Frontend:** Premium dark mobile-first shell; demo fallback when backend unreachable.

## Working features

| Area | Status |
| --- | --- |
| Risk engine + OrderGateway | Working — broad reason codes |
| Paper engine (fees, slippage, WAC, idempotency) | Working |
| EMA strategies + registry | Working |
| Trading orchestrator + offline cycle | Working |
| In-memory PaperSession dashboard | Working (resets on restart) |
| Journal ORMs + CLI attach | Working when session provided |
| Auth (PBKDF2 users, HMAC cookies) | Working |
| Alembic 0001–0004 schema | Applied |
| Premium UI routes | Working |
| CI (ruff, mypy, pytest, FE lint/typecheck/build) | Working |
| docker-compose (Postgres + Redis only) | Present |

## Incomplete features

| Gap | Impact |
| --- | --- |
| Paper portfolio not restored from DB | Restart wipes balances/positions |
| `0004` writers for balances/positions/snapshots unused | Schema idle |
| Dual candle sources (synthetic vs offline) | Divergent signals |
| Backtest bypasses risk gateway | Sim path not unified |
| No backend scheduler | Cycles are on-demand only |
| Legacy `/api/routes.py` placeholders | Stale/fake data if hit |
| No Prometheus `/metrics` | Ops blind |
| No FE Scheduler / System health / Audit journal / Paper-trading pages | Ops UX incomplete |
| No frontend unit tests | Regression risk |
| No application Dockerfiles | Deploy friction |
| Kill-switch: dashboard unauthenticated vs v1 admin-gated | Split brain |
| `.env.example` wrong auth env names | Operator confusion |

## Critical risks

1. **State loss on restart** — operators lose paper history and open exposure view.
2. **Mutating BFF demo fallback** — failed writes can soft-succeed as demo.
3. **Dashboard kill-switch without admin token** — weaker than `/api/v1` controls.
4. **Backtest fill path without risk** — acceptable for research only if clearly labelled; must not feed live paper fills.
5. **Stale docs (phase16)** — claim no CI/compose; outdated.

## Technical debt

- Empty `app/repositories/` and `app/accounting/` packages.
- Journal/auth ORMs defined outside `models/database/`.
- Unused legacy FE layout components.
- Hardcoded `database_ok=True` in `/api/v1/system/status`.
- Redis configured but unused.

## Test status (pre-milestone)

- Backend: substantial unit + integration suite; CI cov gate 70% on risk/execution/portfolio/strategies.
- Frontend: lint/typecheck/build only — **no** `npm test`.
- Residual `__pycache__` test modules without sources on this branch.

## Recommended implementation order

1. Durable paper state (load/save + transactional sync + restart test)
2. Wire journal on API cycles; repository layer over `0004` tables
3. Unified cycle entry + market-data validation/provider health labels
4. Safe scheduler (disabled by default, DB state, locks, admin controls)
5. API hardening (pagination, correlation IDs, admin on sensitive mutators)
6. Frontend pages: Paper trading, Scheduler, System health, Audit journal
7. Analytics from persisted data + metric definitions doc
8. Observability (`/metrics`, real readiness probes) + security review
9. Expand tests + CI (secret scan, FE test script if added) + Dockerfiles
10. Documentation refresh (README, runbooks, readiness checklist remains mostly unchecked)

## Safety baseline (must preserve)

- `TRADING_MODE=paper` default
- No live order execution path enabled
- Every paper fill through `OrderGateway` → `RiskEngine`
- No secrets in frontend bundles
- No profitability guarantees in UI copy
