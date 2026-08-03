# Spot Testnet configuration reference

All values are environment variables (see `.env.example`).

## Required for testnet execution

| Variable | Example | Notes |
|----------|---------|-------|
| `TRADING_MODE` | `paper` | Must stay `paper`. Live money mode is disabled. |
| `EXCHANGE_ENV` | `testnet` | `paper` / `testnet` / `live` (`live` raises at startup) |
| `EXCHANGE_API_KEY` | *(testnet key)* | From https://testnet.binance.vision/ — not production |
| `EXCHANGE_API_SECRET` | *(testnet secret)* | Same |
| `ADMIN_API_TOKEN` | random secret | Required for runtime start + kill switch |

## Endpoints (do not change for execution)

| Variable | Default |
|----------|---------|
| `BINANCE_TESTNET_REST_URL` | `https://testnet.binance.vision` |
| `BINANCE_TESTNET_WS_URL` | `wss://stream.testnet.binance.vision/ws` |

Never point these at `api.binance.com` for order submission.

## Runtime tuning

| Variable | Default | Purpose |
|----------|---------|---------|
| `TESTNET_RECONCILE_SECONDS` | `30` | Portfolio reconcile interval |
| `ORDER_COOLDOWN_SECONDS` | `5` | Min seconds between orders |
| `MARKET_DATA_STALE_SECONDS` | `30` | WS stale → force reconnect |
| `KILL_SWITCH_ENABLED` | `false` | Global halt |
| `PAPER_STARTING_BALANCE` | `10000` | Local seed before first hydrate |
| `WEBHOOK_ALERT_URL` | _(empty)_ | Optional alert webhook |

## Modes

```text
EXCHANGE_ENV=paper   → local paper broker (no network orders)
EXCHANGE_ENV=testnet → Binance Spot Testnet broker + WS
EXCHANGE_ENV=live    → LiveTradingDisabledError (immediate)
```
