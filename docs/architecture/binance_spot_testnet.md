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

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/testnet/status` | Connection + runtime snapshot |
| `GET /api/v1/testnet/diagnostics` | DB/Redis/WS/risk/portfolio probes |
| `GET /api/v1/testnet/dashboard` | Live testnet dashboard payload |
| `POST /api/v1/testnet/cycle/run` | One deterministic cycle (sample candles by default) |
| `POST /api/v1/testnet/runtime/start` | Start runtime (admin token) |
| `POST /api/v1/testnet/kill-switch` | Kill switch (admin token) |

## Factory

`app/execution/factory.py` → `build_execution_backend(settings)`

## Reconciliation

`PortfolioReconciler` every `TESTNET_RECONCILE_SECONDS` compares exchange balances vs local ledger, repairs from exchange, alerts on mismatch.

## Safety

- No production Binance execution endpoints
- No futures / leverage
- No AI order execution
- Live selection always errors
