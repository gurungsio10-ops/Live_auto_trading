# Project Atlas

Safe, deterministic, personal cryptocurrency **paper** trading platform.

**Paper mode is the default.** Live money trading is not implemented. AI is advisory only. Every order passes through one central risk engine (`app/risk/engine.py`).

## Architecture summary

```text
Market data → candle validation → EMA strategy → signal → risk engine
  → paper broker → fill → portfolio (WAC) → journal → /api/v1 → dashboard
```

Key packages: `app/market_data`, `app/strategies`, `app/risk`, `app/execution`, `app/services` (orchestrator + paper cycle), `app/journal`, `app/api`, `frontend/`.

Docs:

- `docs/architecture/current_state_audit.md`
- `docs/architecture/paper_trading_flow.md`
- `docs/architecture/risk_controls.md`
- `docs/architecture/database_schema.md`
- `docs/operations/runbook.md`
- `docs/operations/live_trading_readiness_checklist.md` (**all items unchecked**)

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Keep TRADING_MODE=paper. Set ADMIN_API_TOKEN for kill-switch / paper reset.
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Dashboard:

```bash
cd frontend && npm install
ADMIN_API_TOKEN=local-dev-admin-token ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

## Docker setup

```bash
docker compose up -d   # PostgreSQL + Redis
```

Point `DATABASE_URL` at the compose Postgres instance (asyncpg URL). App processes still run on the host (or your own image) for development.

## Environment variables

See `.env.example`. Critical:

| Variable | Default | Notes |
|----------|---------|-------|
| `TRADING_MODE` | `paper` | Must stay paper for this milestone |
| `KILL_SWITCH_ENABLED` | `false` | Global halt for new orders |
| `ADMIN_API_TOKEN` | (unset) | Required for mutating `/api/v1` system routes |
| `PAPER_STARTING_BALANCE` | `10000` | Quote currency (USDT) |
| `PAPER_FEE_BPS` / `PAPER_SLIPPAGE_BPS` | `10` / `5` | Simulated costs |
| `ALLOWED_SYMBOLS` | `BTC/USDT` | Risk allowlist |
| Risk `*_PERCENT` | see example | Accepts `1` or `0.01` for 1% |

Never commit real secrets.

## Database migrations

```bash
alembic upgrade head   # 0001..0004
```

## Running backend / frontend

```bash
uvicorn app.main:app --reload
npm --prefix frontend run dev
```

Health: `GET /health`, `GET /api/v1/health`, `GET /api/v1/system/status`.

## Run one paper cycle

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/paper/cycle/run \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTC/USDT","timeframe":"1m","strategy_id":"ema_crossover"}'
```

Or use **Run one paper cycle** on the overview dashboard (simulated results only).

CLI offline replay:

```bash
python -m app.cli paper-run --offline --duration-minutes 0
```

## Tests / quality

```bash
pytest -q
ruff check app tests
ruff format --check app tests
mypy app
alembic upgrade head
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

CI: `.github/workflows/ci.yml`.

## Safety model

- Decimal-only money; timezone-aware UTC timestamps
- No secrets in logs (`app/core/security.redact`)
- Kill switch blocks new orders; reads remain available
- Paper reset requires `confirm=RESET_PAPER_ACCOUNT` + admin token
- Live execution raises `LiveTradingDisabledError`

## Paper versus live

| Mode | Status |
|------|--------|
| Paper | Supported end-to-end for BTC/USDT |
| Live | Disabled — see live readiness checklist (unchecked) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Binance HTTP 451 | Geo-block; use `--offline` or another public exchange |
| `no such table` | `alembic upgrade head` |
| Demo banner in UI | Start backend; set `ATLAS_BACKEND_URL` |
| 503 on kill-switch/reset | Set `ADMIN_API_TOKEN` on API (and Next server for reset proxy) |
| Startup fails with live mode | Expected — keep `TRADING_MODE=paper` |

## Binance Spot Testnet (Sprint 1)

See `docs/architecture/binance_spot_testnet.md`.

```bash
# Keys from https://testnet.binance.vision/
EXCHANGE_ENV=testnet
EXCHANGE_API_KEY=...
EXCHANGE_API_SECRET=...
TRADING_MODE=paper   # keep paper — testnet ≠ live money

curl -X POST http://127.0.0.1:8000/api/v1/testnet/cycle/run \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"BTC/USDT","timeframe":"1m","use_sample_candles":true}'
```

`EXCHANGE_ENV=live` / `TRADING_MODE=live` raises `LiveTradingDisabledError`.

Docker: `docker compose up -d` (postgres/redis); `docker compose --profile app up -d` for API.

## Current limitations

- In-memory paper session resets on process restart (journal tables exist for durable audit when wired with a DB session)
- Public Binance may be unreachable from some networks
- Backtests share strategy rules but do not always share the live risk gateway path
- Live order execution is intentionally unimplemented
- Real WS transport must be attached for multi-hour soak (injectable in tests)
- Simulated / backtest / testnet results **do not guarantee future performance**

## Warnings

This is **not** ready for live money. Passing tests validate paper trading only.
