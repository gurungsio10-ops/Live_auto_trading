# Binance Spot Testnet Pipeline

Sprint 1 delivers a production-quality **Binance Spot Testnet** execution path.

```text
Market data (WS kline/trade or sample candles)
  → Strategy (EMA crossover)
  → Risk engine (mandatory)
  → Binance Spot Testnet order
  → Exchange confirmation
  → Local portfolio + journal
  → Dashboard /api/v1/testnet/*
```

## Modes

| `EXCHANGE_ENV` | Backend |
|----------------|---------|
| `paper` | Local paper broker |
| `testnet` | Binance Spot Testnet (`testnet.binance.vision`) |
| `live` | **Raises `LiveTradingDisabledError`** |

`TRADING_MODE` remains `paper` by default. Testnet funds are not live money.

## Configuration

```bash
TRADING_MODE=paper
EXCHANGE_ENV=testnet
EXCHANGE_API_KEY=...          # Spot Testnet key
EXCHANGE_API_SECRET=...
BINANCE_TESTNET_REST_URL=https://testnet.binance.vision
BINANCE_TESTNET_WS_URL=wss://stream.testnet.binance.vision/ws
TESTNET_RECONCILE_SECONDS=30
ORDER_COOLDOWN_SECONDS=5
ADMIN_API_TOKEN=...
```

Create keys at: https://testnet.binance.vision/

## API

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/v1/testnet/status` | none | Connection + runtime snapshot |
| `GET /api/v1/testnet/diagnostics` | none | DB/Redis/WS/risk/portfolio probes |
| `GET /api/v1/testnet/dashboard` | none | Live testnet dashboard payload |
| `POST /api/v1/testnet/cycle/run` | none | One cycle (sample or REST klines) |
| `POST /api/v1/testnet/runtime/start` | `X-Admin-Token` | Start WS + reconciler + hydrate |
| `POST /api/v1/testnet/kill-switch` | `X-Admin-Token` | Kill switch |

### `POST /api/v1/testnet/cycle/run` body

```json
{
  "symbol": "BTC/USDT",
  "timeframe": "1m",
  "use_sample_candles": true,
  "lookback": 60
}
```

- `use_sample_candles=true` — offline EMA fixture (CI/demo).
- `use_sample_candles=false` — REST OHLCV from Spot Testnet, then one strategy cycle. Requires `EXCHANGE_ENV=testnet` + credentials.

Response includes `data_source` (`sample_candles` | `rest_klines`) and `dashboard` snapshot.

## WebSocket

`RealWebSocketTransport` (`websockets`) connects to
`wss://stream.testnet.binance.vision/stream?streams=...@kline_1m/...@trade`.

Features: reconnect, heartbeat/ping, stale watchdog, exponential backoff, trade/kline dedup, REST gap recovery on disconnect.

## Factory

`app/execution/factory.py` → `build_execution_backend(settings)`

## Reconciliation & restart

`PortfolioReconciler` every `TESTNET_RECONCILE_SECONDS` compares exchange balances vs local ledger, repairs from exchange, alerts on mismatch.

On runtime start, balances and open orders are hydrated from the exchange so restarts do not invent divergent spot positions.

## Docs

- Config: `docs/operations/testnet_configuration.md`
- Deploy: `docs/operations/testnet_deployment.md`
- Troubleshoot: `docs/operations/testnet_troubleshooting.md`

## Safety

- No production Binance execution endpoints
- No futures / leverage
- No AI order execution
- Live selection always errors
