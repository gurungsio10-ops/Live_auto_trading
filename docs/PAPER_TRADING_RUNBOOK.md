# Paper Trading Runbook

**Warning:** Profitable backtests or paper results do **not** guarantee live profits. Live money trading is disabled.

## Prerequisites

- Python 3.12+, Node 20+
- Optional: Docker for Postgres/Redis (`docker compose up -d`)

## Environment setup

```bash
cp .env.example .env
# Keep:
#   ATLAS_RUNTIME_MODE=PAPER
#   TRADING_MODE=paper
#   ENABLE_LIVE_TRADING=false
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
npm --prefix frontend ci
```

## Start the project

```bash
# Infra (optional)
docker compose up -d

# Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (another terminal)
ATLAS_BACKEND_URL=http://127.0.0.1:8000 ADMIN_API_TOKEN=local-dev-admin-token \
  npm --prefix frontend run dev
```

Open http://127.0.0.1:3000 — login `admin` / `atlas` (change in shared envs).

## Seed / start paper engine

Paper account seeds automatically from `PAPER_STARTING_BALANCE`.

Run one deterministic cycle (EMA crossover fixture → risk → paper fill):

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/paper/cycle/run \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTC/USDT","timeframe":"1m"}' | jq
```

Or use **Run one paper cycle** on the Overview page.

Offline CLI:

```bash
python -m app.cli paper-run --offline
```

## Pause / kill switch / reset

| Action | How |
|--------|-----|
| Pause | Overview → Pause trading, or `POST /trading/pause` |
| Kill switch | Overview control, or `POST /api/v1/system/kill-switch/activate` with `X-Admin-Token` |
| Reset paper | Overview → Reset (confirm), or `POST /api/v1/paper/reset` with admin token + `{"confirm":"RESET_PAPER_ACCOUNT"}` |

Kill switch state is persisted in `system_state` and restored on restart.

## Inspect trades and logs

- Dashboard: Positions, Orders, Fills, Signals, Risk events
- API: `GET /api/v1/portfolio`, `/orders`, `/fills`, `/signals`, `/risk/decisions`, `/journal`
- Structured JSON logs from uvicorn (secrets redacted)

## Replay fixture data

`POST /api/v1/paper/cycle/run` uses offline EMA crossover candles (no exchange).
Repeat calls for the same candle are idempotent (no duplicate orders).

## Known limitations

- Continuous paper loop is one-shot cycles (not a 24/7 stream by default)
- Fill history in RAM may be empty after restart; balances/positions/kill switch hydrate from DB
- LIVE mode is hard-blocked
- Demo banner appears if the Next.js BFF cannot reach the API

## Quality commands

```bash
ruff check app tests && ruff format --check app tests
mypy app
pytest -q
alembic upgrade head
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```
