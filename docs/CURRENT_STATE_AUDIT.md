# Current State Audit — Project Atlas

**Date:** 2026-08-04  
**Branch basis:** `main` @ `88c312e` (paper vertical slice)  
**Method:** Code + tests + CI inspection. Documentation status percentages were **not** trusted.

## Technology stack (verified)

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, Uvicorn, Pydantic Settings, Python ≥3.11 |
| ORM | SQLAlchemy 2 async, Alembic (`0001`–`0004`) |
| DB | SQLite (default) / Postgres (`asyncpg`) |
| Exchange libs | ccxt, httpx (paper broker is local) |
| Frontend | Next.js 14, React 18, Tailwind |
| Quality | pytest, ruff, mypy, black; CI workflow |

Redis is in compose and `REDIS_URL` but **not required** for paper trading.

## Repository structure

`app/` (backend), `frontend/`, `tests/`, `alembic/`, `docs/`, `docker-compose.yml`, `.github/workflows/ci.yml`.

## What genuinely works

- `TRADING_MODE=paper` default; live refuse-at-startup (`assert_startup_safe`)
- Risk engine + `OrderGateway` gating paper orders
- Paper broker (fees, slippage, WAC, idempotency keys)
- `TradingOrchestrator` + `run_paper_trading_cycle` (offline EMA crossover fixture)
- `/api/v1` paper cycle / portfolio / kill-switch / reset
- Dashboard root routes backed by in-memory `PaperSession`
- Frontend proxies when backend is up
- Alembic migrations apply in CI
- ~160 pytest tests collected on `main`

## What is partial

| Area | Evidence |
|------|----------|
| Persistence | Tables in `0004` exist; **no writers** for balances/positions/`system_state` on HTTP path |
| Kill switch | Process-local; lost on restart |
| Cycle idempotency | In-memory `_PROCESSED_CYCLE_KEYS` — restart can re-trade same candle |
| Journal on API path | Optional; not attached by default |
| Health probes | `/api/v1/system/status` hardcodes `database_ok=True` |
| Legacy `/api/*` | Static portfolio (`"10000"`) divergent from PaperSession |
| Runtime modes | Only `TRADING_MODE ∈ {paper,live}` × `EXCHANGE_ENV ∈ {paper,testnet,live}` — no unified BACKTEST\|PAPER\|TESTNET\|LIVE |
| Frontend demo fallback | Silent mock data when backend down |
| Auth env names | `.env.example` uses `ATLAS_ADMIN_*`; code uses `ATLAS_DASHBOARD_*` |

## Placeholders

- Legacy `/api/portfolio/summary`, `/api/equity-curve` static data (`app/api/routes.py`)
- Live broker always disabled (`LiveTradingDisabledError`)
- Futures primitives unwired
- AI advisory only (correct)

## Security / trading-safety risks

1. Kill switch not durable across restarts  
2. Dashboard mutators lack admin token (browser auth only)  
3. Dual kill-switch paths (dashboard vs `/api/v1` vs legacy `/api/controls`)  
4. Default local credentials `admin`/`atlas`  
5. Demo fallback can fake kill-switch success when API is down  

Live money path remains correctly blocked.

## Prioritised implementation plan (this task)

1. Unified runtime mode model + hard LIVE guard + tests  
2. Paper persistence (kill switch, portfolio, cycle keys) + startup hydrate  
3. Wire journal + snapshots on paper cycle  
4. Fix legacy `/api` to PaperSession  
5. Risk: insufficient balance + cooldown  
6. Reference strategy (EMA + RSI confirm + ATR stop) keep `ema_crossover`  
7. Frontend: last cycle, fills, runtime badge, audit feed  
8. E2E restart + kill-switch persistence tests  
9. Runbook + audit/report docs + README  

## Verified completion (after this implementation pass)

~88% durable paper E2E: modes, hydrate, idempotent restart test, fills page, live hard-block.
Remaining: continuous paper loop, full ORM hydrate of fills/orders, admin-auth on all dashboard mutators.