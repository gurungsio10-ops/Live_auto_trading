# Risk controls

Every order intent is evaluated by `app/risk/engine.py` before any execution path (`OrderGateway`).

## Checks (paper vertical slice)

| Control | Behavior |
|---------|----------|
| Trading mode | Live requires full gate set; live execution not implemented |
| Kill switch | `HALTED` / `KILL_SWITCH_ACTIVE` |
| Allowed symbols | `ALLOWED_SYMBOLS` / `supported_symbols` |
| Side | Buy/sell only; long-only spot |
| Short selling | Rejected unless reducing an existing long |
| Leverage | `default_leverage` must be 1 |
| Balance / exposure | Max position %, portfolio %, risk per trade |
| Daily loss / drawdown | Fraction of peak equity |
| Max open positions | Non-reducing entries capped |
| Market data freshness | `MARKET_DATA_STALE_SECONDS` |
| Quantity / price | Positive; min notional; precision |
| Duplicate / idempotency | Same key rejected |
| Frequency | Max orders per minute |
| Circuit breaker / health flags | Halt or reject |

## Position sizing

Risk may **REDUCE** quantity to fit risk-per-trade / exposure caps (deterministic). It does not silently enlarge. Invalid precision / min size rejects.

## Kill switch

- Config: `KILL_SWITCH_ENABLED`
- Runtime: dashboard / `/api/v1/system/kill-switch/*` (admin token)
- When active: reject new orders; health endpoints expose state; reads allowed
