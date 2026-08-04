# AGENTS.md

## Cursor Cloud specific instructions

Project Atlas is a gated **paper/live crypto trading system** with two services in one repo:

- **Backend** — FastAPI (Python `>=3.11`, runs on 3.12 here). Package config in `pyproject.toml`.
- **Frontend** — `frontend/` Next.js 14 + TypeScript + Tailwind "Atlas Terminal" ops dashboard.

Standard commands are already documented in `README.md` and `frontend/README.md`; the notes below are only the non-obvious caveats discovered while setting up the environment.

### Running the services

- The Python virtualenv lives at `.venv` (created during setup; needs the `python3.12-venv` system package, which is part of the environment image, not the update script). Activate with `source .venv/bin/activate`.
- Backend dev server: `uvicorn app.main:app --reload` (listens on `http://127.0.0.1:8000`). Health check: `GET /health`.
- Frontend dev server: `npm --prefix frontend run dev` (`http://localhost:3000`). It reaches the backend at `ATLAS_BACKEND_URL` (defaults to `http://127.0.0.1:8000`).
- `.env` is copied from `.env.example`; defaults are paper-safe and require **no secrets** to run. `TRADING_MODE` defaults to `paper` — never weaken this or the live-trading gate (see `.cursor/rules/atlas.mdc`).
- Database is **SQLite by default** (`sqlite+aiosqlite:///./atlas.db`); **run `alembic upgrade head`** to create tables (includes the `users` table needed for login). `REDIS_URL` is configured but **Redis is not required** — nothing connects to it at startup.
- **Login is backend-authoritative.** The Next.js middleware still gates routes (unauthenticated pages → `/login`, `/api/*` → `401`), but `frontend/app/api/auth/login` now calls the FastAPI `POST /auth/login`, which verifies against a DB-backed user store with PBKDF2-hashed passwords (`app/auth/`). The backend signs the session token; the middleware verifies it locally, so **`ATLAS_AUTH_SECRET` must match on both sides** (defaults align in dev). Default creds `admin` / `atlas` (override via `ATLAS_DASHBOARD_USER` / `ATLAS_DASHBOARD_PASSWORD`); the admin is seeded on first login. "Remember me" issues a 30-day token/cookie vs 8h default. Because login needs the backend + `users` table, run the backend and `alembic upgrade head` before signing in.

### Test / lint

- Backend: `pytest -q`, `ruff check app tests`, `ruff format --check app tests`, `mypy app`, `alembic upgrade head`.
- Frontend: `npm --prefix frontend run lint`, `npm run typecheck`, `npm run build`. ESLint is configured (`.eslintrc.json`, `eslint@8` + `eslint-config-next@14`).
- Paper vertical slice API lives under `/api/v1/*`. Mutating kill-switch / paper-reset routes require `ADMIN_API_TOKEN` (`X-Admin-Token` header). Set the same token on the Next.js server for `/api/paper/reset`.
- **All dashboard mutators** (`/kill-switch`, `/orders`, `/trading/pause`, strategy select/start/stop/params, backtests, legacy `/api/controls/*`) also require `ADMIN_API_TOKEN`. Next.js BFF routes forward it via `adminHeaders()` from `frontend/lib/backend.ts`. Mutating BFFs **fail closed** (HTTP 503) when the backend is down — they must not invent APPROVED orders or kill-switch success.
- Single-cycle entrypoint: `run_paper_trading_cycle` in `app/services/paper_cycle.py` (EMA crossover 9/21, offline candles by default). Dashboard “Run one paper cycle” proxies to it.
- `GET /ready` probes the database (`SELECT 1`). LIVE runtime always returns `not_ready`. PAPER and TESTNET can be ready when DB is up.
- `LiveTradingGate.evaluate()` never returns `allowed=True` in this phase (hard-blocked). Use `checklist_complete` for readiness inspection; include `LIVE_STARTUP_ACK=I_UNDERSTAND_LIVE_TRADING_RISKS` among checklist conditions.
- Registered strategies: `ema_crossover`, `ema_trend`, `rsi_mean_reversion`, `breakout`.

### Live dashboard data & the demo fallback

The dashboard is now backed by **live root-level backend endpoints** in `app/api/dashboard.py`, served by an in-memory `app/services/paper_session.py` that wires the real risk engine, paper execution engine, strategy registry and backtesting engine. Portfolio, positions, orders, signals, risk-events, equity-curve, strategies (+ select/start/stop/params), kill-switch, pause, settings, journal export and backtests all return real engine computations, so the yellow "Demo data" banner **no longer appears** in normal operation.

Key behaviours to know:
- `PaperSession` is process-local but **hydrated from PostgreSQL/SQLite on startup** (`bootstrap_paper_runtime`): kill switch, trading flags, recon halt, checkpoint + `paper_accounts` / `risk_state` / `strategy_state`, cycle keys, journal (or checkpoint) orders/fills. A restart must not wipe the paper account unless `POST /api/paper/reset` is called with admin auth + `RESET_PAPER_ACCOUNT`.
- After `alembic upgrade head`, revision **`0006_paper_durable`** must be applied for first-class durable tables. Dual-write keeps legacy `system_state` keys for back-compat.
- Startup reconciliation is **fail-closed**: exceptions pause trading and persist a halt. Clear with `POST /api/v1/reconciliation/clear-halt` (admin token; not memory-only `clear_reconciliation_halt()`). Status: `GET /api/v1/recovery/status`.
- `persist_paper_session` stages dual-writes and **commits once**. Cycle persist/recon write failures call `_fail_closed_persistence` (pause + `database_healthy=false` + recon halt) so trading does not continue with divergent memory vs DB.
- `run_paper_trading_cycle` auto-attaches `JournalStore` when `journal` is omitted **except** for `:memory:` SQLite (pytest isolation). Production/file/Postgres paths get durable order/fill ledger writes.
- Authoritative paper-v1 release branch is `cursor/release-paper-v1-consolidated-e3a2` (built from PR **#26**). PRs #21–#25 are superseded ancestors. See `docs/audit/pr_consolidation_audit.md` and `docs/audit/release_merge_plan.md`.
- Recovery dashboard: `/recovery` (BFF `/api/recovery/*`). Clear-halt needs confirm `CLEAR_RECONCILIATION_HALT` + server-side admin token.
- Accounting invariants: `app/accounting/invariants.py` (wired after paper cycles; soak writes `artifacts/soak/invariants.json`).
- Soak harness: `python -m app.cli paper-soak --seed 42` (use `--max-cycles` in CI). No exchange credentials required.
- Coverage gate is **85%** (`pyproject.toml` / CI). Omits advisory/disabled paths (`app/ai/*`, `app/execution/exchange/*`, `app/api/mvp.py`, `app/cli.py`, `app/news/*`, deprecated `market_data/service.py`).
- **Every order still routes through the risk engine** (`OrderGateway` → `app/risk/engine.py`) before the paper engine — nothing bypasses risk checks.
- Canonical cycle path: `run_paper_trading_cycle` with DB cycle locks (`cycle_locks`), journal attachment, post-cycle reconciliation, and fail-closed readiness when reconciliation is unhealthy. See `docs/operations/recovery_runbook.md`.
- Shared DB pool: use `app.db.base.session_scope` / `get_shared_engine` (not per-request `create_engine().dispose()`). `CYCLE_LOCK_FAIL_CLOSED=true` rejects cycles when the lock layer is unavailable.
- MarketDataHub (`app/market_data/hub.py`) is the unified observation interface; funding/OI are **advisory only**. Ops SSE: `GET /ops/stream` (proxied by `frontend/app/api/ops/stream`).
- PortfolioManager (`app/portfolio/manager.py`) wraps PaperSession for period PnL/exposure; leverage remains `1` (spot paper).
- Advisory AI scoring: `POST /api/ai/score-signal` — never submits orders.
- Scheduler is **disabled by default** (`ENABLE_TRADING_SCHEDULER=false`). It persists runs, tracks consecutive failures, and auto-pauses after `SCHEDULER_FAILURE_THRESHOLD`.
- Mutating BFFs **fail closed** (HTTP 503) when the backend/auth is down — they must not invent APPROVED orders or successful cycles. Yellow "Demo data" on GET routes means the backend is unreachable.
- CORS is restricted via `CORS_ALLOWED_ORIGINS`. Live money remains hard-blocked.
