# GitHub Codespaces — Atlas login & paper stack

Paper mode only. Do not enable live trading or attach real exchange keys.

Codespaces **auto-start** the paper development stack when the container starts
(`.devcontainer/devcontainer.json` → `postStartCommand` →
`scripts/codespaces_start.sh` in the background). This is **not** 24/7 hosting:
idle Codespaces stop, and you must reopen / restart services afterward.

## Automatic startup behaviour

On Codespace start:

1. Docker Compose brings up **PostgreSQL** and **Redis** (volumes preserved)
2. Creates `.venv` / installs deps only when needed
3. Creates `.env` and `frontend/.env.local` from examples **only if missing**
4. Runs `alembic upgrade head`
5. Starts FastAPI (`.venv/bin/python -m uvicorn`) on `0.0.0.0:8000`
6. Starts Next.js on `0.0.0.0:3000`
7. Writes PIDs under `.run/` and logs under `.run/logs/`

`postStartCommand` returns immediately; watch progress with:

```bash
tail -f .run/logs/poststart.log
./scripts/codespaces_status.sh
```

## Manual commands

```bash
chmod +x scripts/codespaces_*.sh scripts/run_api.sh
./scripts/codespaces_start.sh     # full stack
./scripts/codespaces_status.sh    # postgres/redis/backend/frontend/health/ports/branch
./scripts/codespaces_stop.sh      # stop apps + compose services (keeps volumes)
./scripts/codespaces_restart.sh   # stop then start
```

`scripts/codespaces_up.sh` remains as a compatibility wrapper around `codespaces_start.sh`.

API only (foreground):

```bash
./scripts/run_api.sh
```

## Open the dashboard

1. Wait until `./scripts/codespaces_status.sh` shows backend health `ok` and port `3000` listening
2. In the Codespaces **Ports** panel, open the forwarded URL for **port 3000**
   (`https://<name>-3000.app.github.dev`)
3. Sign in with the development credentials below

Do **not** point browser JS at `http://127.0.0.1:8000` or at an `http://`
forwarded backend URL from an HTTPS page (mixed content). Prefer the Next.js BFF.

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
| `Docker daemon is not running` | Rebuild/reopen Codespace (Docker-in-Docker feature). Or start Docker manually. |
| `uvicorn: command not found` | Use `.venv/bin/python -m uvicorn` / `./scripts/codespaces_start.sh` |
| `SettingsError` parsing `.env` / `ALLOWED_SYMBOLS` | Keep `ALLOWED_SYMBOLS=BTC/USDT` (comma-separated). Copy fresh `.env.example` if needed. |
| `Authentication service unavailable` | Backend not on `:8000` or BFF `ATLAS_BACKEND_URL` wrong — check `.run/logs/backend.log` |
| Port already in use | `./scripts/codespaces_stop.sh` then start again |
| Auto-start still running | `tail -f .run/logs/poststart.log` |

## Troubleshooting with logs

| Log | Path |
|-----|------|
| Auto-start | `.run/logs/poststart.log` |
| FastAPI | `.run/logs/backend.log` |
| Next.js | `.run/logs/frontend.log` |
| PIDs | `.run/backend.pid`, `.run/frontend.pid` |

```bash
./scripts/codespaces_status.sh
tail -n 100 .run/logs/backend.log
tail -n 100 .run/logs/frontend.log
curl -sf http://127.0.0.1:8000/health | jq .
```

## Environment variables

| Variable | Where | Purpose |
|----------|--------|---------|
| `ATLAS_BACKEND_URL` | frontend `.env.local` (server) | Loopback FastAPI base, default `http://127.0.0.1:8000` |
| `ATLAS_AUTH_SECRET` | backend + frontend (must match) | HMAC session signing |
| `ATLAS_DASHBOARD_USER` / `ATLAS_DASHBOARD_PASSWORD` | backend (seed) | Dev admin seed on first login |
| `ADMIN_API_TOKEN` | backend + frontend | Mutating dashboard actions |
| `DATABASE_URL` | backend / start script | Compose Postgres by default for Codespaces start |
| `REDIS_URL` | backend / start script | Compose Redis by default |
| `CORS_ALLOWED_ORIGINS` | backend | Extra origins; Codespaces frontend origin auto-added when `CODESPACE_NAME` is set |

## Dev credentials (development only)

- Username: `admin`
- Password: `atlas`

Password is stored as PBKDF2 hash in the `users` table after first successful seed.
Never use these defaults on a shared/production host. Startup scripts do **not** print secrets.

## Verification

```bash
./scripts/codespaces_status.sh
curl -sf http://127.0.0.1:8000/health | jq .
curl -sf http://127.0.0.1:8000/ready | jq .
curl -sf -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"atlas"}' | jq .
curl -sf -X POST http://127.0.0.1:3000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"atlas"}' | jq .
```

Then open the forwarded port **3000** URL → sign in → dashboard loads.
Paper trading remains the only enabled mode (`TRADING_MODE=paper`, live hard-blocked).

## Notes

- `codespaces_stop.sh` stops app processes and Compose services; it does **not** delete Docker volumes or databases.
- Repeated `codespaces_start.sh` skips already-running backend/frontend PID-managed processes.
- Live trading, real exchange keys, leverage, futures, and withdrawals remain out of scope.
