# Spot Testnet troubleshooting

## Quick matrix

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `LiveTradingDisabledError` / HTTP 501 | `EXCHANGE_ENV=live` or `TRADING_MODE=live` | Keep `TRADING_MODE=paper`, `EXCHANGE_ENV=testnet` |
| `ConfigurationError` missing keys | No Spot Testnet credentials | Create keys at https://testnet.binance.vision/ and set `EXCHANGE_API_KEY` / `EXCHANGE_API_SECRET` |
| HTTP 400 `use_sample_candles=false requires EXCHANGE_ENV=testnet` | REST cycle called in paper env | Set `EXCHANGE_ENV=testnet` or use `use_sample_candles=true` |
| Orders rejected `quantity_precision` / min notional | Qty below LOT_SIZE / MIN_NOTIONAL | Runtime quantizes via `fetch_symbol_info`; lower size or top up testnet USDT |
| `ORDER_COOLDOWN` | Too frequent cycles | Wait `ORDER_COOLDOWN_SECONDS` (default 5) |
| `KILL_SWITCH_ACTIVE` | Kill switch on | `POST /api/v1/testnet/kill-switch` with admin token, `enabled: false` |
| WS disconnected / stale | Network blip | Auto-reconnect + exponential backoff; REST gap recovery runs on disconnect |
| Portfolio mismatch alert | Local drifted from exchange | `PortfolioReconciler` auto-repairs from exchange every `TESTNET_RECONCILE_SECONDS` |
| Dashboard empty | Runtime never started / no cycle | `POST /api/v1/testnet/runtime/start` or `cycle/run` |
| Geo / HTTP 451 on public Binance | Region block | Spot **Testnet** host differs; if still blocked, use sample-candle cycles offline |

## Data sources

1. **Sample candles** (`use_sample_candles=true`) — offline deterministic EMA fixture; safe for CI/demo.
2. **REST klines** (`use_sample_candles=false`) — pulls Spot Testnet OHLCV via ccxt sandbox, then runs one cycle.
3. **WebSocket stream** — after `runtime/start`, `RealWebSocketTransport` connects to `stream.testnet.binance.vision` and processes closed 1m klines continuously.

## Restart behavior

On `runtime/start`, balances and open orders are hydrated from the exchange (source of truth). Process-local signal/fill history resets; exchange positions survive.

## Health

`GET /api/v1/testnet/diagnostics` reports DB, Redis, WS, risk, portfolio reconcile, and last execution latency.
