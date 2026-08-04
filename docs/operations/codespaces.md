# GitHub Codespaces — Atlas login & paper stack

Paper mode only. Do not enable live trading or attach real exchange keys.

## Root cause of “Authentication service unavailable”

The browser posts to **same-origin** `POST /api/auth/login` (good for Codespaces HTTPS).
That Next.js route then calls FastAPI `POST /auth/login` at **`ATLAS_BACKEND_URL`**
(default `http://127.0.0.1:8000`) **from the Codespace container**.

The UI shows *Authentication service unavailable* when that server-side hop fails
(backend down, wrong `DATABASE_URL`, migrations missing, or timeout) — **not** when
the password is wrong (wrong password returns *Invalid username or password*).

## Common startup failures

| Error | Fix |
|-------|-----|
| `uvicorn: command not found` | Use the venv: `source .venv/bin/activate` or `.venv/bin/uvicorn …` / `./scripts/run_api.sh` |
| `SettingsError` parsing `.env` / `ALLOWED_SYMBOLS` | Fixed in settings (`NoDecode`). Keep `ALLOWED_SYMBOLS=BTC/USDT` (comma-separated, not unquoted JSON). Copy fresh `.env.example` if needed. |
| `Authentication service unavailable` | Backend not on `:8000` or BFF `ATLAS_BACKEND_URL` wrong — start API first |

## One-command bring-up

```bash
chmod +x scripts/codespaces_up.sh scripts/run_api.sh
./scripts/codespaces_up.sh
```

API only:

```bash
./scripts/run_api.sh
```

Or manually:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp -n .env.example .env
cp -n frontend/.env.example frontend/.env.local
export TRADING_MODE=paper ENABLE_LIVE_TRADING=false
export ATLAS_AUTH_SECRET=atlas-dev-secret-change-me
export ATLAS_DASHBOARD_USER=admin ATLAS_DASHBOARD_PASSWORD=atlas
export ADMIN_API_TOKEN=local-dev-admin-token
export ATLAS_BACKEND_URL=http://127.0.0.1:8000
# Postgres (compose defaults) or SQLite:
# export DATABASE_URL=postgresql+asyncpg://atlas:atlas@127.0.0.1:5432/atlas
alembic upgrade head

.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# separate terminal:
npm --prefix frontend run dev -- --hostname 0.0.0.0 --port 3000
```

## URLs

| What | Where |
|------|--------|
| Open in browser | Codespaces **Forwarded port 3000** HTTPS URL (`https://<name>-3000.app.github.dev`) |
| Backend (private) | `http://127.0.0.1:8000` inside the Codespace (BFF uses this) |
| Optional backend proxy | `https://<frontend>/api/backend/<path>` → FastAPI |

Do **not** point browser JS at `http://127.0.0.1:8000` or at an `http://` forwarded backend URL from an HTTPS page (mixed content). Prefer the Next.js BFF.

## Environment variables

| Variable | Where | Purpose |
|----------|--------|---------|
| `ATLAS_BACKEND_URL` | frontend `.env.local` (server) | Loopback FastAPI base, default `http://127.0.0.1:8000` |
| `ATLAS_AUTH_SECRET` | backend + frontend (must match) | HMAC session signing |
| `ATLAS_DASHBOARD_USER` / `ATLAS_DASHBOARD_PASSWORD` | backend (seed) | Dev admin seed on first login |
| `ADMIN_API_TOKEN` | backend + frontend | Mutating dashboard actions |
| `DATABASE_URL` | backend | Postgres or SQLite |
| `CORS_ALLOWED_ORIGINS` | backend | Extra origins; Codespaces frontend origin auto-added when `CODESPACE_NAME` is set |

## Dev credentials (development only)

- Username: `admin`
- Password: `atlas`

Password is stored as PBKDF2 hash in the `users` table after first successful seed.
Never use these defaults on a shared/production host.

## Verification

```bash
curl -sf http://127.0.0.1:8000/health | jq .
curl -sf http://127.0.0.1:8000/ready | jq .
curl -sf -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"atlas"}' | jq .
curl -sf -X POST http://127.0.0.1:3000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"atlas"}' | jq .
# invalid password → 401
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:3000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"wrong"}'
```

Then open the forwarded port **3000** URL → sign in → dashboard loads.
Paper trading remains the only enabled mode (`TRADING_MODE=paper`, live hard-blocked).
