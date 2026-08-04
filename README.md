# Project Atlas

Safe, deterministic, personal cryptocurrency **paper** trading platform.

**Paper mode is the default.** Live money trading is hard-blocked. AI is advisory only. Every order passes through one central risk engine (`app/risk/engine.py`).

Banner: **PAPER TRADING — NO REAL FUNDS**

## Architecture

```text
Market data → candle validation → EMA(+RSI) strategy → signal → risk engine
  → paper broker → fill → portfolio (WAC) → journal → /api + /api/v1 → dashboard
```

See `docs/architecture/system_overview.md`, `docs/audit/repository_consolidation_report.md`,
`docs/audit/final_verification_report.md`, and `SECURITY.md`.

## Quick start (Makefile)

```bash
python -m venv .venv && source .venv/bin/activate
make setup
make migrate
make dev                 # FastAPI on :8000
# other terminal:
make frontend-dev        # Next.js on :3000
make paper-cycle         # one simulated trade cycle
make test
make lint
make typecheck
```

## Manual setup

```bash
pip install -e ".[dev]"
cp .env.example .env
# Keep TRADING_MODE=paper, TRADING_ENABLED=false, ENABLE_LIVE_TRADING=false
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Dashboard:

```bash
cd frontend && npm ci
ADMIN_API_TOKEN=local-dev-admin-token ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000 — login `admin` / `atlas` (dev defaults).

## Paper cycle (MVP API)

```bash
# One-shot cycle (works even when TRADING_ENABLED=false)
curl -s -X POST http://127.0.0.1:8000/api/trading/cycle \
  -H 'Content-Type: application/json' \
  -H "X-Admin-Token: local-dev-admin-token" \
  -d '{"confirm":"RUN_ONE_CYCLE","symbol":"BTC/USDT","timeframe":"5m"}'

# Or enable continuous paper mode, then cycle without one-shot confirm:
curl -s -X POST http://127.0.0.1:8000/api/trading/start \
  -H 'Content-Type: application/json' \
  -H "X-Admin-Token: local-dev-admin-token" \
  -d '{"confirm":"START_PAPER_TRADING"}'
```

Legacy path still works: `POST /api/v1/paper/cycle/run`.

## Docker

```bash
docker compose up -d          # Postgres + Redis
docker build -t atlas-api .   # optional API image (paper-only env)
```

## Safety

| Control | Default |
|---------|---------|
| `TRADING_MODE` | `paper` |
| `TRADING_ENABLED` | `false` |
| `ENABLE_LIVE_TRADING` | `false` |
| Futures / leverage / withdrawals | blocked by `SafetyGuard` |
| Live order submission | hard-blocked |

Never commit real API keys. Mutating controls require `ADMIN_API_TOKEN`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `401` on cycle/kill-switch | Set `ADMIN_API_TOKEN` and send `X-Admin-Token` |
| Yellow “Demo data” banner | Backend unreachable — start uvicorn |
| `409 TRADING_ENABLED is false` | Pass `confirm=RUN_ONE_CYCLE` or call `/api/trading/start` |
| LIVE startup error | Keep `TRADING_MODE=paper` |
