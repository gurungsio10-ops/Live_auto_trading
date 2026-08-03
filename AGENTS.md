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
- Database is **SQLite by default** (`sqlite+aiosqlite:///./atlas.db`); run `alembic upgrade head` to create tables. `REDIS_URL` is configured but **Redis is not required** — nothing connects to it at startup.
- The dashboard is behind a **login gate** (Next.js middleware). Any unauthenticated page request redirects to `/login`, and `/api/*` proxy calls return `401` until signed in. Default demo credentials are `admin` / `atlas` (override via `ATLAS_DASHBOARD_USER` / `ATLAS_DASHBOARD_PASSWORD`; the session cookie is signed with `ATLAS_AUTH_SECRET`). Auth lives entirely in the frontend (`frontend/middleware.ts`, `frontend/lib/auth.ts`, `frontend/app/api/auth/*`) — the FastAPI backend is unauthenticated.

### Test / lint

- Backend tests: `pytest -q` (108 tests pass). Backend lint: `ruff check .` — note the repo currently has many pre-existing ruff findings and no ruff config; the linter runs, but treat those findings as the repo's existing state, not setup breakage.
- Frontend: `next lint` interactively prompts to configure ESLint (not set up in this repo). For a non-interactive static check use `npx tsc --noEmit` inside `frontend/` (passes clean). `npm --prefix frontend run build` also type-checks.

### Non-obvious: frontend "Demo data" banner is expected, not a failure

The frontend is intentionally resilient: every `frontend/app/api/*` proxy route falls back to demo/mock data (showing a yellow "Demo data — backend unavailable or endpoint missing" banner) whenever its backend call fails. The current FastAPI backend implements only a **subset** of the endpoints the dashboard calls, and mounts them under the `/api` prefix with different names (e.g. backend `GET /api/portfolio/summary`, `POST /api/controls/kill-switch`), while the frontend's `backendFetch` targets root-level paths like `/portfolio`, `/kill-switch`, `/positions`, `/backtests`, etc. Only `/health` and `/config/safe` line up, so the Overview health badge and Settings view show live backend data while the other views show demo data. Backend `404 Not Found` log lines for `/portfolio`, `/strategies`, etc. are the frontend probing endpoints that don't exist yet — this is by design and does **not** indicate a broken environment.
