# Spot Testnet deployment guide

## Prerequisites

1. Binance Spot Testnet account + API key: https://testnet.binance.vision/
2. Python 3.12, Node 20
3. Docker (postgres/redis)

## Configure

```bash
cp .env.example .env
# Set:
TRADING_MODE=paper
EXCHANGE_ENV=testnet
EXCHANGE_API_KEY=...
EXCHANGE_API_SECRET=...
ADMIN_API_TOKEN=...
DATABASE_URL=postgresql+asyncpg://atlas:atlas@localhost:5432/atlas
```

## Start

```bash
docker compose up -d
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
ADMIN_API_TOKEN=... ATLAS_BACKEND_URL=http://127.0.0.1:8000 npm --prefix frontend run dev
```

## Verify

```bash
curl -s http://127.0.0.1:8000/api/v1/testnet/status | jq
curl -s http://127.0.0.1:8000/api/v1/testnet/diagnostics | jq

# Offline deterministic cycle (no exchange network required for market data)
curl -s -X POST http://127.0.0.1:8000/api/v1/testnet/cycle/run \
  -H 'Content-Type: application/json' \
  -d '{"use_sample_candles":true}' | jq

# One-shot cycle from Spot Testnet REST klines
curl -s -X POST http://127.0.0.1:8000/api/v1/testnet/cycle/run \
  -H 'Content-Type: application/json' \
  -d '{"use_sample_candles":false,"lookback":60}' | jq

# Continuous WS + reconciler (admin token)
curl -s -X POST http://127.0.0.1:8000/api/v1/testnet/runtime/start \
  -H "X-Admin-Token: $ADMIN_API_TOKEN" | jq
```

## Troubleshooting

See `docs/operations/testnet_troubleshooting.md` and `docs/operations/testnet_configuration.md`.

## Soak / restart

`POST /api/v1/testnet/runtime/start` connects `RealWebSocketTransport` to Spot Testnet streams, starts the 30s portfolio reconciler, and **hydrates balances/open orders from the exchange** so a process restart re-syncs ledger state. Keep `docker compose` Postgres/Redis up; run `alembic upgrade head` for journal tables.