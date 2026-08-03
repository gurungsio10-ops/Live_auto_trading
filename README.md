# Project Atlas

Gated paper/live crypto trading system. **Paper mode is the default.** Live
trading requires every condition in `docs/architecture/roadmap.md` simultaneously.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pytest -q
uvicorn app.main:app --reload
```

Dashboard:

```bash
cd frontend && npm install && npm run dev
```

## Safety

- `TRADING_MODE` defaults to `paper`
- All orders pass through `app/risk/engine.py`
- Use `Decimal` for money; UTC for timestamps
- Never log secrets — use `app/core/security.redact`
- AI (`app/ai/`) is advisory only

See `.cursor/rules/atlas.mdc` and `docs/architecture/roadmap.md`.

## Paper-trading validation (Phase 16)

End-to-end, deterministic paper trading with **no live orders**. See
`docs/architecture/paper_trading_data_flow.md` and the audit under `docs/audit/`.

### Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"        # backend
cp .env.example .env
(cd frontend && npm install)   # dashboard
```

### Database migrations

```bash
alembic upgrade head           # applies 0001..0003 to a clean SQLite DB (./atlas.db)
```

### Run the services (dev)

```bash
uvicorn app.main:app --reload                 # backend  -> http://127.0.0.1:8000
npm --prefix frontend run dev                 # dashboard -> http://localhost:3000
```

### Offline deterministic replay (no network)

```bash
pytest -q tests/integration/test_paper_trading_replay.py
```

Proves the full pipeline (candle → indicators → strategy → risk → paper fill →
portfolio → journal → metrics) with a completed trade, idempotent replay, and
kill-switch blocking.

### Public-data paper-run

```bash
# Deterministic, offline (works anywhere; completes a paper trade):
python -m app.cli paper-run --offline --duration-minutes 0

# Real public data (choose a reachable ccxt exchange; NO credentials needed):
python -m app.cli paper-run --exchange kraken --symbol BTC/USD --interval 1m --duration-minutes 2

# Phase-16 safety posture (all orders halted):
KILL_SWITCH_ENABLED=true python -m app.cli paper-run --offline --duration-minutes 0
```

Note: `--exchange binance` may return HTTP 451 from restricted locations; pick a
reachable public exchange (e.g. `kraken`, `coinbase`, `kucoin`). The command uses
**public** market-data endpoints only and never submits a live order.

### Expected output

A `PAPER MODE` banner then a session summary with: candles received/rejected,
signals, HOLD decisions, risk approvals/rejections, paper orders, fills, fees,
realized/unrealized P&L, current balance, equity, max drawdown, open positions,
errors. With the kill switch enabled, `paper_orders`/`fills` are `0` and
`risk_rejections` is non-zero (orders `HALTED`).

### Docker

No `docker-compose.yml`/`Dockerfile` ships yet (tracked in the Phase-16 audit).
Run the services directly as above.

### Troubleshooting

- **`451` from Binance:** geo-restricted; use `--exchange kraken` (or another).
- **`no such table` on login/journal:** run `alembic upgrade head`.
- **Dashboard shows a yellow "Demo data" banner:** the backend is unreachable —
  start `uvicorn app.main:app` (normal operation shows live data).
- **`next lint` prompts to configure ESLint:** use `npx tsc --noEmit` in `frontend/`.

### Warnings

- **Profitability is not guaranteed.** The bundled strategy and sample market are
  for validation, not trading advice.
- **Passing tests do not make this platform live-trading ready.** Phase 16 validates
  paper trading only. Live trading remains gated off and unreachable; testnet soak
  and live readiness are separate later phases.
