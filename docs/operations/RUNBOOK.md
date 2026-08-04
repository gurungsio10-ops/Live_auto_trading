# Operations Runbook — Project Atlas (Paper)

**Warning:** This platform is paper-first. Live money trading is hard-blocked. Simulated or backtest profits do **not** guarantee future performance.

Canonical short paper runbook also lives at `docs/PAPER_TRADING_RUNBOOK.md`. This file is the expanded ops runbook (`RUNBOOK.md`).

## Prerequisites

- Python 3.12+, Node 20+
- Optional: Docker Engine + Compose for Postgres/Redis
- **Note:** Some cloud/dev VMs have **no `docker` CLI**. Local SQLite (`DATABASE_URL=sqlite+aiosqlite:///./atlas.db`) is enough for paper development. CI validates `docker compose config` on runners that have Docker.

## Local start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Keep:
#   ATLAS_RUNTIME_MODE=PAPER
#   TRADING_MODE=paper
#   ENABLE_LIVE_TRADING=false
#   ADMIN_API_TOKEN=local-dev-admin-token
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend (separate terminal):

```bash
cd frontend && npm ci
ADMIN_API_TOKEN=local-dev-admin-token ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Open http://127.0.0.1:3000 — default dashboard login from `.env.example` is `admin` / `atlas` (change for any shared environment).

## Docker Compose notes

```bash
docker compose up -d   # postgres:16 + redis:7
```

- Compose provides **data plane only** (no app image in-repo). Run API/UI on the host.
- Point `DATABASE_URL` at Postgres with an async driver URL when using compose.
- Default Redis URL is `redis://localhost:6379/0`; paper REST mode does not require Redis to be healthy for basic cycles.
- If `docker` is missing: skip compose; use SQLite defaults from `.env.example`.

## Run one paper cycle

API (offline fixture path; no exchange required for the default cycle):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/paper/cycle/run \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTC/USDT","timeframe":"1m","strategy_id":"ema_crossover"}'
```

Dashboard: Overview → **Run one paper cycle**.

CLI offline replay:

```bash
python -m app.cli paper-run --offline --duration-minutes 0
```

Repeat calls for the same candle are idempotent (cycle keys persisted in `system_state`).

## Kill switch

Activate (blocks new orders; reads remain available):

```bash
curl -X POST http://127.0.0.1:8000/api/v1/system/kill-switch/activate \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"ops halt"}'
```

Dashboard Overview also exposes kill-switch / pause controls (BFF forwards `X-Admin-Token`).

Kill-switch state is persisted and restored on process restart.

## Paper reset

```bash
curl -X POST http://127.0.0.1:8000/api/v1/paper/reset \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"confirm":"RESET_PAPER_ACCOUNT"}'
```

Wrong or missing confirmation string is rejected. Admin token required.

## Admin token

| Rule | Behavior |
|------|----------|
| Header | `X-Admin-Token: <token>` or `Authorization: Bearer <token>` |
| Env | `ADMIN_API_TOKEN` on API **and** Next server for mutator proxies |
| Unset | Mutating endpoints return **503** (fail closed) |
| Wrong | **401** |

Used for kill switch, paper reset, dashboard mutators (orders, strategy start/stop, pause, backtests, etc.).

## Health / ready

| Endpoint | Meaning |
|----------|---------|
| `GET /health`, `GET /health/live` | Process up; reports mode + kill switch |
| `GET /ready`, `GET /health/ready` | Readiness: **DB probe** (`SELECT 1`); LIVE always `not_ready` |
| `GET /api/v1/health`, `GET /api/v1/ready` | Versioned monitoring surface |
| `GET /api/v1/system/status` | Broader status (includes DB probe where wired) |
| `GET /config/safe` | Redacted config for operators |

Graceful shutdown disposes SQLAlchemy engines in app lifespan.

## Quality gates (local)

```bash
ruff check app tests && ruff format --check app tests
mypy app
pytest -q
alembic upgrade head
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

CI: `.github/workflows/ci.yml` (backend lint/type/test/migrate, frontend lint/typecheck/build, Gitleaks secret scan, compose config validation).

## Troubleshooting

| Symptom | Check |
|---------|-------|
| 503 on kill-switch / reset / mutators | `ADMIN_API_TOKEN` unset on API (and BFF for proxied calls) |
| 401 on mutators | Wrong admin token |
| Binance HTTP 451 | Geo-block; use `--offline` paper cycle / CLI |
| `no such table` | `alembic upgrade head` |
| Demo banner in UI | Backend unreachable; set `ATLAS_BACKEND_URL`; start uvicorn |
| Startup fails with LIVE / live trading | Expected — keep paper mode; LIVE is hard-blocked |
| `docker: command not found` | Use SQLite; skip compose locally |
| Ready → `database probe failed` | Fix `DATABASE_URL` / run migrations / ensure DB file writable |
| Kill switch “on” after restart | Persisted in `system_state` — deactivate deliberately |

## Related

- `docs/operations/INCIDENT_RESPONSE.md`
- `docs/operations/live_trading_readiness_checklist.md` (go-live items unchecked)
- `docs/USER_GUIDE.md`
