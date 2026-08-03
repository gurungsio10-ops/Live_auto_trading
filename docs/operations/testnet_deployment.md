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
curl -s -X POST http://127.0.0.1:8000/api/v1/testnet/cycle/run \
  -H 'Content-Type: application/json' \
  -d '{"use_sample_candles":true}' | jq
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ConfigurationError` credentials | Set Spot **Testnet** keys (not production) |
| `LiveTradingDisabledError` | Set `EXCHANGE_ENV=testnet` and `TRADING_MODE=paper` |
| Orders rejected precision | Symbol filters loaded from exchange; check min notional |
| WS not connected | Attach real transport or use sample-candle cycles |
| Portfolio mismatch alerts | Expected on first reconcile; auto-repair from exchange |

## Soak

For continuous operation, attach a production WS transport to `BinanceSpotTestnetWebSocket` and keep reconciler running. Restart-safe state uses Postgres journal tables after `alembic upgrade head`.
