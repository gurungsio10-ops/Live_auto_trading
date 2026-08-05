# AGENTS.md

## Cursor Cloud specific instructions

Project Atlas is a gated **paper/live crypto trading system** with two services in one repo:

- **Backend** — FastAPI (Python `>=3.11`, runs on 3.12 here). Package config in `pyproject.toml`.
- **Frontend** — `frontend/` Next.js 14 + TypeScript + Tailwind paper-trading dashboard (premium dark fintech UI). Route map and design tokens are in `frontend/README.md` and `docs/ui/UX_GUIDELINES.md`.

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
- Frontend: `npm --prefix frontend run lint`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run test`, `npm --prefix frontend run build`. ESLint is configured (`.eslintrc.json`, `eslint@8` + `eslint-config-next@14`). No dedicated frontend unit-test framework yet — `npm test` runs a secret-exposure smoke check.
- Tailwind gotcha: use `text-foreground` / `text-brand` for copy colours — `text-primary` clashes with the primary button colour scale.
- Paper portfolio state is **durable** (hydrate on startup / persist after mutations). Run `alembic upgrade head` (through `0006_paper_durable`). Scheduler is **disabled by default** (`SCHEDULER_ENABLED=false`) and never starts live trading.
- New ops UI routes: `/paper-trading`, `/scheduler`, `/system-health`, `/audit`. Admin-gated scheduler/reset use server-side `ADMIN_API_TOKEN` only.
- Paper vertical slice API lives under `/api/v1/*`. Mutating kill-switch / paper-reset routes require `ADMIN_API_TOKEN` (`X-Admin-Token` header). Set the same token on the Next.js server for `/api/paper/reset`.
- Single-cycle entrypoint: `run_paper_trading_cycle` in `app/services/paper_cycle.py` (EMA crossover 9/21, offline candles by default). Dashboard “Run one paper cycle” proxies to it.

### Live dashboard data & the demo fallback

The dashboard is now backed by **live root-level backend endpoints** in `app/api/dashboard.py`, served by an in-memory `app/services/paper_session.py` that wires the real risk engine, paper execution engine, strategy registry and backtesting engine. Portfolio, positions, orders, signals, risk-events, equity-curve, strategies (+ select/start/stop/params), kill-switch, pause, settings, journal export and backtests all return real engine computations, so the yellow "Demo data" banner **no longer appears** in normal operation.

Key behaviours to know:
- The `PaperSession` is **in-memory and resets when the backend restarts** (fresh $10,000 paper account, no positions).
- **Every order still routes through the risk engine** (`OrderGateway`) before the paper engine — nothing bypasses risk checks. Reduce-only exits pass a tight protective stop so risk sizing permits a full close (all safety gates still apply).
- Starting a strategy (`POST /strategies/{id}/start`) runs one paper "tick": it synthesises a deterministic candle series, evaluates the strategy, and if it signals BUY/EXIT places a risk-checked paper order. The market series is engineered so the EMA-trend strategy produces a genuine (non-overbought) entry.
- The frontend proxy routes **still fall back to demo/mock data** if the backend is genuinely unreachable — so a yellow "Demo data" banner now means the backend is actually down, not a normal state.
